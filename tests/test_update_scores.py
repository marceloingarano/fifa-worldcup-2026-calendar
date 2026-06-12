"""Tests for update_scores.py — OpenLigaDB integration, matching, and score processing."""

import json
from pathlib import Path

import pytest

from update_scores import (
    load_scores,
    save_scores,
    resolve_team_name,
    find_match_number,
    extract_final_score,
    determine_status,
    process_api_data,
    TEAM_SHORT_TO_NAME,
)


@pytest.fixture
def temp_scores(tmp_path, monkeypatch):
    temp_file = tmp_path / "scores.json"
    monkeypatch.setattr("update_scores.SCORES_FILE", temp_file)
    return temp_file


@pytest.fixture
def sample_matches():
    return [
        {"match_number": 7, "home": "Brazil", "away": "Morocco", "date": "2026-06-13"},
        {"match_number": 8, "home": "Haiti", "away": "Scotland", "date": "2026-06-13"},
        {"match_number": 1, "home": "Mexico", "away": "South Africa", "date": "2026-06-11"},
    ]


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


class TestFindMatchNumber:
    def test_exact_match(self, sample_matches):
        result = find_match_number(sample_matches, "Brazil", "Morocco", "2026-06-13")
        assert result == 7

    def test_reversed_teams(self, sample_matches):
        result = find_match_number(sample_matches, "Morocco", "Brazil", "2026-06-13")
        assert result == 7

    def test_wrong_date_returns_none(self, sample_matches):
        result = find_match_number(sample_matches, "Brazil", "Morocco", "2026-06-14")
        assert result is None

    def test_unknown_teams_returns_none(self, sample_matches):
        result = find_match_number(sample_matches, "Spain", "Italy", "2026-06-13")
        assert result is None


class TestExtractFinalScore:
    def test_finished_match(self, api_match_finished):
        home, away = extract_final_score(api_match_finished)
        assert home == 2
        assert away == 0

    def test_live_match_returns_halftime(self, api_match_live):
        home, away = extract_final_score(api_match_live)
        assert home == 1
        assert away == 0

    def test_not_started_returns_none(self, api_match_not_started):
        home, away = extract_final_score(api_match_not_started)
        assert home is None
        assert away is None


class TestDetermineStatus:
    def test_finished(self, api_match_finished):
        assert determine_status(api_match_finished) == "FT"

    def test_live(self, api_match_live):
        assert determine_status(api_match_live) == "LIVE"

    def test_not_started(self, api_match_not_started):
        assert determine_status(api_match_not_started) == "NS"


class TestProcessApiData:
    def test_processes_finished_match(self, sample_matches, api_match_finished):
        scores = {}
        updated = process_api_data([api_match_finished], sample_matches, scores)
        assert updated == 1
        assert scores["7"]["score_home"] == 2
        assert scores["7"]["score_away"] == 0
        assert scores["7"]["status"] == "FT"

    def test_processes_live_match(self, sample_matches, api_match_live):
        scores = {}
        updated = process_api_data([api_match_live], sample_matches, scores)
        assert updated == 1
        assert scores["7"]["status"] == "LIVE"

    def test_skips_not_started(self, sample_matches, api_match_not_started):
        scores = {}
        updated = process_api_data([api_match_not_started], sample_matches, scores)
        assert updated == 0

    def test_only_finished_skips_live(self, sample_matches, api_match_live):
        scores = {}
        updated = process_api_data([api_match_live], sample_matches, scores, only_finished=True)
        assert updated == 0

    def test_does_not_update_if_same(self, sample_matches, api_match_finished):
        scores = {"7": {"score_home": 2, "score_away": 0, "status": "FT"}}
        updated = process_api_data([api_match_finished], sample_matches, scores)
        assert updated == 0

    def test_updates_if_score_changed(self, sample_matches, api_match_finished):
        scores = {"7": {"score_home": 1, "score_away": 0, "status": "LIVE"}}
        updated = process_api_data([api_match_finished], sample_matches, scores)
        assert updated == 1
        assert scores["7"]["score_home"] == 2


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
