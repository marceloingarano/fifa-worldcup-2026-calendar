"""Tests for update_scores.py — orchestration: apply_records, fallback, I/O.

Per-source parsing lives in test_source_espn.py / test_source_openligadb.py;
matching lives in test_score_matching.py. This file covers only the
source-agnostic glue.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import update_scores
from score_sources import ScoreRecord, espn, openligadb
from update_scores import apply_records, load_scores, save_scores


@pytest.fixture
def temp_scores(tmp_path, monkeypatch):
    temp_file = tmp_path / "scores.json"
    monkeypatch.setattr("update_scores.SCORES_FILE", temp_file)
    return temp_file


@pytest.fixture
def sample_matches():
    return [
        {"match_number": 2, "home": "South Korea", "away": "Czech Republic",
         "date": "2026-06-11", "time": "20:00", "timezone": "America/Mexico_City"},
        {"match_number": 7, "home": "Brazil", "away": "Morocco",
         "date": "2026-06-13", "time": "18:00", "timezone": "America/New_York"},
    ]


def _record(home, away, utc, sh, sa, status):
    return ScoreRecord(home=home, away=away, utc=utc, score_home=sh, score_away=sa, status=status)


# Brazil vs Morocco kicks off 2026-06-13 18:00 ET = 22:00 UTC.
BRA_UTC = datetime(2026, 6, 13, 22, 0, tzinfo=timezone.utc)
# Korea vs Czech kicks off 2026-06-11 20:00 Mexico City = 2026-06-12 02:00 UTC.
KOR_UTC = datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)


class TestLoadSaveScores:
    def test_load_empty_file(self, temp_scores):
        temp_scores.write_text("{}")
        assert load_scores() == {}

    def test_load_nonexistent_returns_empty(self, temp_scores):
        assert load_scores() == {}

    def test_save_creates_file(self, temp_scores):
        save_scores({"1": {"score_home": 1, "score_away": 0, "status": "FT"}})
        assert temp_scores.exists()
        assert json.loads(temp_scores.read_text())["1"]["score_home"] == 1


class TestApplyRecords:
    def test_applies_finished_record(self, sample_matches):
        scores = {}
        updated = apply_records([_record("Brazil", "Morocco", BRA_UTC, 2, 0, "FT")], sample_matches, scores)
        assert updated == 1
        assert scores["7"] == {"score_home": 2, "score_away": 0, "status": "FT"}

    def test_applies_live_record(self, sample_matches):
        scores = {}
        updated = apply_records([_record("Brazil", "Morocco", BRA_UTC, 1, 0, "LIVE")], sample_matches, scores)
        assert updated == 1
        assert scores["7"]["status"] == "LIVE"

    def test_resolves_match_crossing_utc_midnight(self, sample_matches):
        # Regression: Korea vs Czech, UTC date != local date. Must still match #2.
        scores = {}
        updated = apply_records([_record("South Korea", "Czech Republic", KOR_UTC, 0, 1, "LIVE")], sample_matches, scores)
        assert updated == 1
        assert scores["2"] == {"score_home": 0, "score_away": 1, "status": "LIVE"}

    def test_idempotent_when_unchanged(self, sample_matches):
        scores = {"7": {"score_home": 2, "score_away": 0, "status": "FT"}}
        updated = apply_records([_record("Brazil", "Morocco", BRA_UTC, 2, 0, "FT")], sample_matches, scores)
        assert updated == 0

    def test_updates_when_score_changed(self, sample_matches):
        scores = {"7": {"score_home": 1, "score_away": 0, "status": "LIVE"}}
        updated = apply_records([_record("Brazil", "Morocco", BRA_UTC, 2, 0, "FT")], sample_matches, scores)
        assert updated == 1
        assert scores["7"]["score_home"] == 2

    def test_unmatched_record_skipped(self, sample_matches):
        scores = {}
        updated = apply_records([_record("Spain", "Italy", BRA_UTC, 1, 1, "FT")], sample_matches, scores)
        assert updated == 0
        assert scores == {}


class TestLiveFallback:
    def test_uses_espn_when_available(self, sample_matches, temp_scores, monkeypatch):
        monkeypatch.setattr(update_scores, "load_matches", lambda: sample_matches)
        monkeypatch.setattr(espn, "fetch", lambda today: [_record("Brazil", "Morocco", BRA_UTC, 3, 1, "FT")])
        called = {"openliga": False}
        monkeypatch.setattr(openligadb, "fetch", lambda: called.__setitem__("openliga", True) or [])

        update_scores.cmd_live()

        assert called["openliga"] is False  # ESPN had data, no fallback
        assert load_scores()["7"]["score_home"] == 3

    def test_falls_back_to_openligadb_when_espn_empty(self, sample_matches, temp_scores, monkeypatch):
        monkeypatch.setattr(update_scores, "load_matches", lambda: sample_matches)
        monkeypatch.setattr(espn, "fetch", lambda today: [])
        monkeypatch.setattr(openligadb, "fetch", lambda: [_record("Brazil", "Morocco", BRA_UTC, 0, 0, "FT")])

        update_scores.cmd_live()

        assert load_scores()["7"] == {"score_home": 0, "score_away": 0, "status": "FT"}


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
