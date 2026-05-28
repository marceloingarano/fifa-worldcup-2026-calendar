"""Tests for update_scores.py — score loading, saving, rate limiting, and team matching."""

import json
from datetime import date
from pathlib import Path

import pytest

from update_scores import (
    load_scores,
    save_scores,
    load_usage,
    save_usage,
    check_rate_limit,
    normalize_team_name,
    find_match_number,
    process_api_fixtures,
    DAILY_LIMIT,
)


@pytest.fixture
def temp_scores(tmp_path, monkeypatch):
    temp_file = tmp_path / "scores.json"
    monkeypatch.setattr("update_scores.SCORES_FILE", temp_file)
    return temp_file


@pytest.fixture
def temp_usage(tmp_path, monkeypatch):
    temp_file = tmp_path / ".api_usage.json"
    monkeypatch.setattr("update_scores.USAGE_FILE", temp_file)
    return temp_file


@pytest.fixture
def sample_matches():
    return [
        {"match_number": 7, "home": "Brazil", "away": "Morocco", "date": "2026-06-13"},
        {"match_number": 8, "home": "Haiti", "away": "Scotland", "date": "2026-06-13"},
        {"match_number": 1, "home": "Mexico", "away": "South Africa", "date": "2026-06-11"},
    ]


class TestLoadSaveScores:
    def test_load_empty_file(self, temp_scores):
        temp_scores.write_text("{}")
        assert load_scores() == {}

    def test_load_with_data(self, temp_scores):
        data = {"7": {"score_home": 2, "score_away": 0, "status": "FT"}}
        temp_scores.write_text(json.dumps(data))
        assert load_scores()["7"]["score_home"] == 2

    def test_load_nonexistent_returns_empty(self, temp_scores):
        assert load_scores() == {}

    def test_save_creates_file(self, temp_scores):
        save_scores({"1": {"score_home": 1, "score_away": 0, "status": "FT"}})
        assert temp_scores.exists()
        assert json.loads(temp_scores.read_text())["1"]["score_home"] == 1


class TestRateLimiting:
    def test_under_limit_returns_true(self):
        usage = {"date": str(date.today()), "count": 0, "calls": []}
        assert check_rate_limit(usage) is True

    def test_at_limit_returns_false(self):
        usage = {"date": str(date.today()), "count": DAILY_LIMIT, "calls": []}
        assert check_rate_limit(usage) is False

    def test_over_limit_returns_false(self):
        usage = {"date": str(date.today()), "count": DAILY_LIMIT + 10, "calls": []}
        assert check_rate_limit(usage) is False

    def test_usage_resets_on_new_day(self, temp_usage):
        old_data = {"date": "2026-01-01", "count": 99, "calls": []}
        temp_usage.write_text(json.dumps(old_data))
        usage = load_usage()
        assert usage["count"] == 0
        assert usage["date"] == str(date.today())

    def test_usage_persists_same_day(self, temp_usage):
        today_data = {"date": str(date.today()), "count": 42, "calls": []}
        temp_usage.write_text(json.dumps(today_data))
        usage = load_usage()
        assert usage["count"] == 42


class TestNormalizeTeamName:
    def test_usa_variants(self):
        assert normalize_team_name("USA") == "United States"

    def test_korea(self):
        assert normalize_team_name("Korea Republic") == "South Korea"

    def test_turkey_variants(self):
        assert normalize_team_name("Turkiye") == "Turkey"
        assert normalize_team_name("Türkiye") == "Turkey"

    def test_ivory_coast(self):
        assert normalize_team_name("Côte d'Ivoire") == "Ivory Coast"
        assert normalize_team_name("Cote D'Ivoire") == "Ivory Coast"

    def test_bosnia(self):
        assert normalize_team_name("Bosnia Herzegovina") == "Bosnia and Herzegovina"
        assert normalize_team_name("Bosnia & Herzegovina") == "Bosnia and Herzegovina"

    def test_dr_congo(self):
        assert normalize_team_name("Congo DR") == "DR Congo"

    def test_curacao(self):
        assert normalize_team_name("Curacao") == "Curaçao"

    def test_czechia(self):
        assert normalize_team_name("Czechia") == "Czech Republic"

    def test_already_correct_passes_through(self):
        assert normalize_team_name("Brazil") == "Brazil"
        assert normalize_team_name("France") == "France"
        assert normalize_team_name("Argentina") == "Argentina"


class TestFindMatchNumber:
    def test_exact_match(self, sample_matches):
        result = find_match_number(sample_matches, "Brazil", "Morocco", "2026-06-13")
        assert result == 7

    def test_reversed_teams_still_matches(self, sample_matches):
        result = find_match_number(sample_matches, "Morocco", "Brazil", "2026-06-13")
        assert result == 7

    def test_normalized_name_matches(self, sample_matches):
        result = find_match_number(sample_matches, "Brazil", "Morocco", "2026-06-13")
        assert result == 7

    def test_wrong_date_returns_none(self, sample_matches):
        result = find_match_number(sample_matches, "Brazil", "Morocco", "2026-06-14")
        assert result is None

    def test_unknown_teams_returns_none(self, sample_matches):
        result = find_match_number(sample_matches, "Spain", "Italy", "2026-06-13")
        assert result is None


class TestProcessApiFixtures:
    def test_processes_finished_match(self, sample_matches):
        scores = {}
        api_data = {
            "response": [{
                "fixture": {
                    "date": "2026-06-13T18:00:00+00:00",
                    "status": {"short": "FT", "elapsed": 90}
                },
                "teams": {
                    "home": {"name": "Brazil"},
                    "away": {"name": "Morocco"}
                },
                "goals": {"home": 2, "away": 0}
            }]
        }
        updated = process_api_fixtures(api_data, sample_matches, scores)
        assert updated == 1
        assert scores["7"]["score_home"] == 2
        assert scores["7"]["score_away"] == 0
        assert scores["7"]["status"] == "FT"

    def test_processes_live_match(self, sample_matches):
        scores = {}
        api_data = {
            "response": [{
                "fixture": {
                    "date": "2026-06-13T18:00:00+00:00",
                    "status": {"short": "2H", "elapsed": 67}
                },
                "teams": {
                    "home": {"name": "Brazil"},
                    "away": {"name": "Morocco"}
                },
                "goals": {"home": 1, "away": 0}
            }]
        }
        updated = process_api_fixtures(api_data, sample_matches, scores)
        assert updated == 1
        assert scores["7"]["status"] == "2H"

    def test_skips_matches_without_goals(self, sample_matches):
        scores = {}
        api_data = {
            "response": [{
                "fixture": {
                    "date": "2026-06-13T18:00:00+00:00",
                    "status": {"short": "NS", "elapsed": None}
                },
                "teams": {
                    "home": {"name": "Brazil"},
                    "away": {"name": "Morocco"}
                },
                "goals": {"home": None, "away": None}
            }]
        }
        updated = process_api_fixtures(api_data, sample_matches, scores)
        assert updated == 0
        assert len(scores) == 0

    def test_does_not_update_if_same_score(self, sample_matches):
        scores = {"7": {
            "score_home": 2, "score_away": 0, "status": "FT",
            "api_home": "Brazil", "api_away": "Morocco"
        }}
        api_data = {
            "response": [{
                "fixture": {
                    "date": "2026-06-13T18:00:00+00:00",
                    "status": {"short": "FT", "elapsed": 90}
                },
                "teams": {
                    "home": {"name": "Brazil"},
                    "away": {"name": "Morocco"}
                },
                "goals": {"home": 2, "away": 0}
            }]
        }
        updated = process_api_fixtures(api_data, sample_matches, scores)
        assert updated == 0

    def test_unmatched_fixture_warns(self, sample_matches, capsys):
        scores = {}
        api_data = {
            "response": [{
                "fixture": {
                    "date": "2026-06-20T18:00:00+00:00",
                    "status": {"short": "FT", "elapsed": 90}
                },
                "teams": {
                    "home": {"name": "Unknown FC"},
                    "away": {"name": "Mystery United"}
                },
                "goals": {"home": 1, "away": 1}
            }]
        }
        updated = process_api_fixtures(api_data, sample_matches, scores)
        assert updated == 0
        captured = capsys.readouterr()
        assert "WARN" in captured.out


class TestScoresJsonIntegrity:
    def test_scores_json_is_valid(self):
        path = Path(__file__).parent.parent / "scores.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_score_keys_are_valid_match_numbers(self):
        path = Path(__file__).parent.parent / "scores.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in data:
            assert key.isdigit(), f"Score key '{key}' is not a valid match number"
            assert 1 <= int(key) <= 104, f"Score key '{key}' out of range 1-104"
