"""Tests for score_sources/espn.py — ESPN event parsing and ScoreRecord output."""

from datetime import date, datetime, timezone

import pytest

from score_sources import ScoreRecord, espn
from score_sources.espn import (
    determine_espn_status,
    resolve_espn_name,
    to_record,
)


def _event(state, home_name, home_score, away_name, away_score, date_str="2026-06-12T02:00Z"):
    """Build an ESPN event payload mirroring the real scoreboard shape."""
    return {
        "date": date_str,
        "competitions": [{
            "status": {"type": {"state": state}},
            "competitors": [
                {"homeAway": "home", "score": home_score,
                 "team": {"displayName": home_name, "abbreviation": "HOM"}},
                {"homeAway": "away", "score": away_score,
                 "team": {"displayName": away_name, "abbreviation": "AWY"}},
            ],
        }],
    }


@pytest.fixture
def event_live():
    # Korea 0 x 1 Czechia, second half — the real case that exposed OpenLigaDB's lag.
    return _event("in", "South Korea", "0", "Czechia", "1")


@pytest.fixture
def event_finished():
    return _event("post", "Mexico", "2", "South Africa", "0", "2026-06-11T19:00Z")


@pytest.fixture
def event_not_started():
    return _event("pre", "Canada", None, "Bosnia-Herzegovina", None, "2026-06-12T19:00Z")


class TestResolveEspnName:
    def test_divergent_names_mapped_to_canonical(self):
        assert resolve_espn_name({"team": {"displayName": "Czechia"}}) == "Czech Republic"
        assert resolve_espn_name({"team": {"displayName": "Bosnia-Herzegovina"}}) == "Bosnia and Herzegovina"
        assert resolve_espn_name({"team": {"displayName": "Congo DR"}}) == "DR Congo"
        assert resolve_espn_name({"team": {"displayName": "Türkiye"}}) == "Turkey"

    def test_matching_names_pass_through(self):
        assert resolve_espn_name({"team": {"displayName": "Brazil"}}) == "Brazil"
        assert resolve_espn_name({"team": {"displayName": "South Korea"}}) == "South Korea"


class TestDetermineEspnStatus:
    def test_states(self):
        assert determine_espn_status({"status": {"type": {"state": "post"}}}) == "FT"
        assert determine_espn_status({"status": {"type": {"state": "in"}}}) == "LIVE"
        assert determine_espn_status({"status": {"type": {"state": "pre"}}}) == "NS"

    def test_unknown_state_defaults_ns(self):
        assert determine_espn_status({"status": {"type": {"state": "weird"}}}) == "NS"
        assert determine_espn_status({}) == "NS"


class TestToRecord:
    def test_live_event_record(self, event_live):
        record = to_record(event_live)
        assert isinstance(record, ScoreRecord)
        # ESPN's "Czechia" must be normalized to the matches.json name.
        assert record.home == "South Korea"
        assert record.away == "Czech Republic"
        assert record.score_home == 0
        assert record.score_away == 1
        assert record.status == "LIVE"
        assert record.utc == datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)

    def test_finished_event_record(self, event_finished):
        record = to_record(event_finished)
        assert record.status == "FT"
        assert (record.score_home, record.score_away) == (2, 0)

    def test_not_started_returns_none(self, event_not_started):
        assert to_record(event_not_started) is None

    def test_missing_competitor_returns_none(self):
        bad = {"date": "2026-06-12T02:00Z", "competitions": [{
            "status": {"type": {"state": "in"}},
            "competitors": [{"homeAway": "home", "score": "1", "team": {"displayName": "Brazil"}}],
        }]}
        assert to_record(bad) is None


class TestFetchWindow:
    def test_fetches_today_and_yesterday(self, monkeypatch):
        """fetch() must query both the given UTC day and the day before."""
        seen_days = []

        def fake_fetch_day(day):
            seen_days.append(day)
            return []

        monkeypatch.setattr(espn, "_fetch_day", fake_fetch_day)
        espn.fetch(date(2026, 6, 12))
        assert seen_days == [date(2026, 6, 12), date(2026, 6, 11)]

    def test_filters_not_started(self, monkeypatch):
        def fake_fetch_day(day):
            if day == date(2026, 6, 12):
                return [_event("in", "South Korea", "0", "Czechia", "1"),
                        _event("pre", "Canada", None, "Bosnia-Herzegovina", None)]
            return []

        monkeypatch.setattr(espn, "_fetch_day", fake_fetch_day)
        records = espn.fetch(date(2026, 6, 12))
        assert len(records) == 1
        assert records[0].away == "Czech Republic"
