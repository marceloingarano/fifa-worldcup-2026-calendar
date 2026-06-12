"""Tests for score_sources/openligadb.py — payload parsing and ScoreRecord output."""

from datetime import datetime, timezone

import pytest

from score_sources import ScoreRecord
from score_sources.openligadb import (
    TEAM_SHORT_TO_NAME,
    determine_status,
    extract_final_score,
    resolve_team_name,
    to_record,
)


@pytest.fixture
def api_match_finished():
    return {
        "matchIsFinished": True,
        "matchDateTimeUTC": "2026-06-13T22:00:00Z",
        "team1": {"teamName": "Brasilien", "shortName": "BRA"},
        "team2": {"teamName": "Marokko", "shortName": "MAR"},
        # Mirror real OpenLigaDB ordering: Halbzeit (half-time) is the FIRST
        # chronological result (resultOrderID 1), Endergebnis (final) comes
        # after. extract_final_score() must pick Endergebnis, not orderID 1.
        "matchResults": [
            {"resultOrderID": 1, "resultName": "Halbzeit", "resultTypeID": 1,
             "pointsTeam1": 1, "pointsTeam2": 0},
            {"resultOrderID": 2, "resultName": "Endergebnis", "resultTypeID": 2,
             "pointsTeam1": 2, "pointsTeam2": 0},
        ],
        "goals": [],
    }


@pytest.fixture
def api_match_live():
    return {
        "matchIsFinished": False,
        "matchDateTimeUTC": "2026-06-13T22:00:00Z",
        "team1": {"teamName": "Brasilien", "shortName": "BRA"},
        "team2": {"teamName": "Marokko", "shortName": "MAR"},
        "matchResults": [
            {"resultOrderID": 1, "resultName": "Halbzeit", "resultTypeID": 1,
             "pointsTeam1": 1, "pointsTeam2": 0},
        ],
        "goals": [],
    }


@pytest.fixture
def api_match_not_started():
    return {
        "matchIsFinished": False,
        "matchDateTimeUTC": "2026-06-13T22:00:00Z",
        "team1": {"teamName": "Brasilien", "shortName": "BRA"},
        "team2": {"teamName": "Marokko", "shortName": "MAR"},
        "matchResults": [],
        "goals": [],
    }


class TestResolveTeamName:
    def test_known_short_codes(self):
        match = {"team1": {"teamName": "Brasilien", "shortName": "BRA"}}
        assert resolve_team_name(match, "team1") == "Brazil"

    def test_all_48_teams_mapped(self):
        expected_teams = {
            "Mexico", "South Africa", "South Korea", "Czech Republic",
            "Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland",
            "Brazil", "Morocco", "Haiti", "Scotland",
            "United States", "Paraguay", "Australia", "Turkey",
            "Germany", "Curaçao", "Ivory Coast", "Ecuador",
            "Netherlands", "Japan", "Sweden", "Tunisia",
            "Belgium", "Egypt", "Iran", "New Zealand",
            "Spain", "Cape Verde", "Saudi Arabia", "Uruguay",
            "France", "Senegal", "Iraq", "Norway",
            "Argentina", "Algeria", "Austria", "Jordan",
            "Portugal", "DR Congo", "Uzbekistan", "Colombia",
            "England", "Croatia", "Ghana", "Panama",
        }
        mapped = set(TEAM_SHORT_TO_NAME.values())
        missing = expected_teams - mapped
        assert not missing, f"Teams not in TEAM_SHORT_TO_NAME: {missing}"

    def test_unknown_code_falls_back_to_german_name(self):
        match = {"team1": {"teamName": "UnknownTeam", "shortName": "UNK"}}
        assert resolve_team_name(match, "team1") == "UnknownTeam"


class TestExtractFinalScore:
    def test_finished_match(self, api_match_finished):
        assert extract_final_score(api_match_finished) == (2, 0)

    def test_live_match_returns_halftime(self, api_match_live):
        assert extract_final_score(api_match_live) == (1, 0)

    def test_not_started_returns_none(self, api_match_not_started):
        assert extract_final_score(api_match_not_started) == (None, None)


class TestDetermineStatus:
    def test_finished(self, api_match_finished):
        assert determine_status(api_match_finished) == "FT"

    def test_live(self, api_match_live):
        assert determine_status(api_match_live) == "LIVE"

    def test_not_started(self, api_match_not_started):
        assert determine_status(api_match_not_started) == "NS"


class TestToRecord:
    def test_finished_match_record(self, api_match_finished):
        record = to_record(api_match_finished)
        assert isinstance(record, ScoreRecord)
        assert record.home == "Brazil"
        assert record.away == "Morocco"
        assert record.score_home == 2
        assert record.score_away == 0
        assert record.status == "FT"
        assert record.utc == datetime(2026, 6, 13, 22, 0, tzinfo=timezone.utc)

    def test_live_match_record(self, api_match_live):
        record = to_record(api_match_live)
        assert record.status == "LIVE"
        assert (record.score_home, record.score_away) == (1, 0)

    def test_not_started_returns_none(self, api_match_not_started):
        assert to_record(api_match_not_started) is None
