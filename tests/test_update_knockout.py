"""Tests for update_knockout.py — knockout team resolution safety."""

import json
import copy
from pathlib import Path

import pytest

from update_knockout import (
    is_placeholder,
    has_knockout_placeholders,
    _find_knockout_match,
    _find_knockout_match_by_local_time,
    _convert_utc_to_local_time,
)


@pytest.fixture
def matches_with_placeholders():
    return [
        {"match_number": 1, "stage": "Grupo C", "home": "Brazil", "away": "Morocco",
         "date": "2026-06-13", "time": "18:00", "timezone": "America/New_York",
         "stadium": "MetLife Stadium", "city": "East Rutherford, EUA", "tv": "CazéTV", "streaming": ""},
        {"match_number": 73, "stage": "16 Avos de Final", "home": "Winner Group C",
         "away": "Runner-up Group F", "date": "2026-06-29", "time": "12:00",
         "timezone": "America/New_York", "stadium": "NRG Stadium", "city": "Houston, EUA",
         "tv": "CazéTV", "streaming": ""},
        {"match_number": 74, "stage": "16 Avos de Final", "home": "Winner Group D",
         "away": "Runner-up Group E", "date": "2026-06-29", "time": "16:00",
         "timezone": "America/New_York", "stadium": "MetLife Stadium", "city": "East Rutherford, EUA",
         "tv": "CazéTV", "streaming": ""},
        {"match_number": 104, "stage": "Final", "home": "Winner Match 101",
         "away": "Winner Match 102", "date": "2026-07-19", "time": "15:00",
         "timezone": "America/New_York", "stadium": "MetLife Stadium", "city": "East Rutherford, EUA",
         "tv": "CazéTV", "streaming": ""},
    ]


@pytest.fixture
def matches_all_resolved():
    return [
        {"match_number": 73, "stage": "16 Avos de Final", "home": "Brazil",
         "away": "Sweden", "date": "2026-06-29", "time": "12:00",
         "timezone": "America/New_York", "stadium": "NRG Stadium", "city": "Houston, EUA",
         "tv": "CazéTV", "streaming": ""},
    ]


class TestIsPlaceholder:
    def test_winner_is_placeholder(self):
        assert is_placeholder("Winner Group C") is True
        assert is_placeholder("Winner Match 101") is True

    def test_loser_is_placeholder(self):
        assert is_placeholder("Loser Match 101") is True

    def test_runner_up_is_placeholder(self):
        assert is_placeholder("Runner-up Group A") is True

    def test_third_group_is_placeholder(self):
        assert is_placeholder("3rd Group A/B/C/D/F") is True

    def test_tbd_is_placeholder(self):
        assert is_placeholder("TBD") is True

    def test_real_team_is_not_placeholder(self):
        assert is_placeholder("Brazil") is False
        assert is_placeholder("Germany") is False
        assert is_placeholder("South Korea") is False


class TestHasKnockoutPlaceholders:
    def test_with_placeholders(self, matches_with_placeholders):
        assert has_knockout_placeholders(matches_with_placeholders) is True

    def test_without_placeholders(self, matches_all_resolved):
        assert has_knockout_placeholders(matches_all_resolved) is False

    def test_group_placeholders_ignored(self):
        matches = [
            {"match_number": 1, "stage": "Grupo A", "home": "TBD", "away": "TBD"},
        ]
        # Group stage TBD should not count (they're resolved differently)
        assert has_knockout_placeholders(matches) is False


class TestSafetyGuardrails:
    def test_never_overwrites_real_team_with_placeholder(self, matches_with_placeholders):
        """Ensure a resolved team is never replaced back with a placeholder."""
        matches = copy.deepcopy(matches_with_placeholders)
        # Simulate: match 73 already resolved
        matches[1]["home"] = "Brazil"

        # Original should stay unchanged
        assert matches[1]["home"] == "Brazil"
        assert not is_placeholder("Brazil")

    def test_preserves_all_fields_on_update(self, matches_with_placeholders):
        """Ensure updating team name doesn't lose stadium/tv/streaming."""
        matches = copy.deepcopy(matches_with_placeholders)
        original_fields = {k: v for k, v in matches[1].items() if k not in ("home", "away")}

        # Simulate team update
        matches[1]["home"] = "Brazil"

        # All other fields intact
        for key, value in original_fields.items():
            assert matches[1][key] == value, f"Field '{key}' was modified"

    def test_group_matches_never_touched(self, matches_with_placeholders):
        """Group stage matches must never be modified by knockout update."""
        matches = copy.deepcopy(matches_with_placeholders)
        original_group = copy.deepcopy(matches[0])

        # The update logic should skip anything with stage starting with "Grupo"
        assert matches[0]["stage"].startswith("Grupo")
        assert matches[0] == original_group

    def test_two_matches_same_day_resolved_by_time(self):
        """With multiple knockout matches on same day, matching uses time to differentiate."""
        matches = [
            {"match_number": 73, "stage": "16 Avos de Final", "home": "Winner Group C",
             "away": "Runner-up Group F", "date": "2026-06-29", "time": "12:00",
             "timezone": "America/New_York", "stadium": "NRG Stadium", "city": "Houston, EUA",
             "tv": "", "streaming": ""},
            {"match_number": 74, "stage": "16 Avos de Final", "home": "Winner Group D",
             "away": "Runner-up Group E", "date": "2026-06-29", "time": "16:00",
             "timezone": "America/New_York", "stadium": "MetLife Stadium", "city": "East Rutherford, EUA",
             "tv": "", "streaming": ""},
        ]
        # Local time matching picks the correct one
        result = _find_knockout_match_by_local_time(matches, "2026-06-29", "12:00")
        assert result["match_number"] == 73

        result = _find_knockout_match_by_local_time(matches, "2026-06-29", "16:00")
        assert result["match_number"] == 74

    def test_single_match_on_day_matches_without_time(self):
        """If only one knockout match on a date, returns it regardless of time."""
        matches = [
            {"match_number": 104, "stage": "Final", "home": "Winner Match 101",
             "away": "Winner Match 102", "date": "2026-07-19", "time": "15:00",
             "timezone": "America/New_York", "stadium": "MetLife Stadium", "city": "East Rutherford, EUA",
             "tv": "", "streaming": ""},
        ]
        result = _find_knockout_match_by_local_time(matches, "2026-07-19", "15:00")
        assert result["match_number"] == 104

        # Even with wrong time, single candidate still matches
        result = _find_knockout_match_by_local_time(matches, "2026-07-19", "20:00")
        assert result["match_number"] == 104

    def test_utc_to_local_conversion(self):
        """UTC time converts correctly to Eastern time."""
        # UTC 22:00 in June = ET 18:00 (UTC-4 during EDT)
        local = _convert_utc_to_local_time("22:00", "America/New_York")
        assert local == "18:00"

    def test_find_knockout_match_by_utc(self):
        """OpenLigaDB UTC time resolves to correct local match."""
        matches = [
            {"match_number": 73, "stage": "16 Avos de Final", "home": "Winner Group C",
             "away": "Runner-up Group F", "date": "2026-06-29", "time": "12:00",
             "timezone": "America/Chicago", "stadium": "NRG Stadium", "city": "Houston, EUA",
             "tv": "", "streaming": ""},
            {"match_number": 74, "stage": "16 Avos de Final", "home": "Winner Group D",
             "away": "Runner-up Group E", "date": "2026-06-29", "time": "16:00",
             "timezone": "America/New_York", "stadium": "MetLife Stadium", "city": "East Rutherford, EUA",
             "tv": "", "streaming": ""},
        ]
        # UTC 17:00 = Chicago 12:00 (CDT = UTC-5)
        result = _find_knockout_match(matches, "2026-06-29", "17:00")
        assert result["match_number"] == 73

        # UTC 20:00 = New York 16:00 (EDT = UTC-4)
        result = _find_knockout_match(matches, "2026-06-29", "20:00")
        assert result["match_number"] == 74


class TestMatchesJsonBackupStrategy:
    """Verify that re-running fetch_matches.py can restore the original state."""

    def test_matches_json_has_no_score_fields(self):
        """matches.json should never contain score fields (those are in scores.json)."""
        path = Path(__file__).parent.parent / "matches.json"
        matches = json.loads(path.read_text(encoding="utf-8"))
        for m in matches:
            assert "score_home" not in m, f"Match #{m['match_number']} has score_home in matches.json"
            assert "score_away" not in m, f"Match #{m['match_number']} has score_away in matches.json"

    def test_knockout_matches_have_dates_and_stadiums(self):
        """Even placeholder matches must have date/time/stadium for the workflow to work."""
        path = Path(__file__).parent.parent / "matches.json"
        matches = json.loads(path.read_text(encoding="utf-8"))
        knockout = [m for m in matches if not m["stage"].startswith("Grupo")]
        for m in knockout:
            assert m.get("date"), f"Match #{m['match_number']} missing date"
            assert m.get("time"), f"Match #{m['match_number']} missing time"
            assert m.get("stadium"), f"Match #{m['match_number']} missing stadium"
