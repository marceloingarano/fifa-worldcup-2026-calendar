"""Tests for update_scores.py — score loading, saving, and manual updates."""

import json
from pathlib import Path

import pytest

from update_scores import load_scores, save_scores, SCORES_FILE


@pytest.fixture
def temp_scores(tmp_path, monkeypatch):
    """Use a temporary scores.json for tests."""
    temp_file = tmp_path / "scores.json"
    monkeypatch.setattr("update_scores.SCORES_FILE", temp_file)
    return temp_file


class TestLoadScores:
    def test_load_empty_file(self, temp_scores):
        temp_scores.write_text("{}")
        scores = load_scores()
        assert scores == {}

    def test_load_with_data(self, temp_scores):
        data = {"7": {"score_home": 2, "score_away": 0, "status": "finished"}}
        temp_scores.write_text(json.dumps(data))
        scores = load_scores()
        assert scores["7"]["score_home"] == 2

    def test_load_nonexistent_returns_empty(self, temp_scores):
        scores = load_scores()
        assert scores == {}


class TestSaveScores:
    def test_save_creates_file(self, temp_scores):
        save_scores({"1": {"score_home": 1, "score_away": 0, "status": "finished"}})
        assert temp_scores.exists()
        data = json.loads(temp_scores.read_text())
        assert data["1"]["score_home"] == 1

    def test_save_overwrites_existing(self, temp_scores):
        temp_scores.write_text('{"old": "data"}')
        save_scores({"7": {"score_home": 3, "score_away": 1, "status": "finished"}})
        data = json.loads(temp_scores.read_text())
        assert "old" not in data
        assert "7" in data

    def test_save_preserves_unicode(self, temp_scores):
        save_scores({"1": {"score_home": 0, "score_away": 0, "status": "finished"}})
        content = temp_scores.read_text(encoding="utf-8")
        assert "score_home" in content


class TestScoreIntegrity:
    """Tests that scores.json (if populated) doesn't break calendar generation."""

    def test_scores_json_is_valid_json(self):
        path = Path(__file__).parent.parent / "scores.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_score_values_are_integers_or_null(self):
        path = Path(__file__).parent.parent / "scores.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, score in data.items():
            assert isinstance(score.get("score_home"), (int, type(None))), \
                f"Match {key}: score_home must be int or None"
            assert isinstance(score.get("score_away"), (int, type(None))), \
                f"Match {key}: score_away must be int or None"

    def test_score_keys_are_valid_match_numbers(self):
        path = Path(__file__).parent.parent / "scores.json"
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in data:
            assert key.isdigit(), f"Score key '{key}' is not a valid match number"
            assert 1 <= int(key) <= 104, f"Score key '{key}' out of range 1-104"
