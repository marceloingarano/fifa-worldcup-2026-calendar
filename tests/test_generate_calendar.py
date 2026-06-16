"""Tests for generate_calendar.py — event title, description, location, and merge logic."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar

from generate_calendar import (
    build_event_title,
    build_event_description,
    build_event_location,
    create_calendar,
    add_match_event,
    load_scores,
    merge_scores,
)


@pytest.fixture
def match_no_score():
    return {
        "match_number": 7,
        "stage": "Grupo C",
        "home": "Brazil",
        "away": "Morocco",
        "date": "2026-06-13",
        "time": "18:00",
        "timezone": "America/New_York",
        "stadium": "MetLife Stadium",
        "city": "East Rutherford, EUA",
        "score_home": None,
        "score_away": None,
        "tv": "CazéTV",
        "streaming": "https://www.youtube.com/@CazeTV",
    }


@pytest.fixture
def match_with_score():
    return {
        "match_number": 7,
        "stage": "Grupo C",
        "home": "Brazil",
        "away": "Morocco",
        "date": "2026-06-13",
        "time": "18:00",
        "timezone": "America/New_York",
        "stadium": "MetLife Stadium",
        "city": "East Rutherford, EUA",
        "score_home": 2,
        "score_away": 0,
        "tv": "CazéTV",
        "streaming": "https://www.youtube.com/@CazeTV",
    }


@pytest.fixture
def match_knockout_tbd():
    return {
        "match_number": 104,
        "stage": "Final",
        "home": "Winner Match 101",
        "away": "Winner Match 102",
        "date": "2026-07-19",
        "time": "15:00",
        "timezone": "America/New_York",
        "stadium": "MetLife Stadium",
        "city": "East Rutherford, EUA",
        "score_home": None,
        "score_away": None,
        "tv": "CazéTV",
        "streaming": "",
    }


class TestBuildEventTitle:
    def test_no_score_shows_vs(self, match_no_score):
        title = build_event_title(match_no_score)
        assert "vs" in title
        assert "BRASIL" in title
        assert "Marrocos" in title
        assert "Grupo C" in title
        assert "x" not in title

    def test_with_score_shows_result(self, match_with_score):
        title = build_event_title(match_with_score)
        assert "2 x 0" in title
        assert "vs" not in title
        assert "BRASIL" in title
        assert "Marrocos" in title

    def test_flags_present(self, match_no_score):
        title = build_event_title(match_no_score)
        assert "\U0001f1e7\U0001f1f7" in title  # Brazil flag
        assert "\U0001f1f2\U0001f1e6" in title  # Morocco flag

    def test_knockout_tbd_teams(self, match_knockout_tbd):
        title = build_event_title(match_knockout_tbd)
        assert "Winner Match 101" in title
        assert "Final" in title

    def test_score_zero_zero_shows_correctly(self, match_no_score):
        match_no_score["score_home"] = 0
        match_no_score["score_away"] = 0
        title = build_event_title(match_no_score)
        assert "0 x 0" in title


class TestBuildEventDescription:
    def test_contains_stage(self, match_no_score):
        desc = build_event_description(match_no_score)
        assert "Grupo C" in desc

    def test_contains_match_number(self, match_no_score):
        desc = build_event_description(match_no_score)
        assert "Jogo #7" in desc

    def test_contains_time_with_timezone(self, match_no_score):
        desc = build_event_description(match_no_score)
        assert "18:00" in desc
        assert "ET" in desc

    def test_contains_tv(self, match_no_score):
        desc = build_event_description(match_no_score)
        assert "CazéTV" in desc

    def test_contains_streaming_link(self, match_no_score):
        desc = build_event_description(match_no_score)
        assert "https://www.youtube.com/@CazeTV" in desc

    def test_no_streaming_if_empty(self, match_knockout_tbd):
        desc = build_event_description(match_knockout_tbd)
        assert "🔗" not in desc

    def test_no_tv_if_empty(self):
        match = {
            "match_number": 1, "stage": "Grupo A", "home": "Mexico",
            "away": "South Africa", "date": "2026-06-11", "time": "13:00",
            "timezone": "America/Mexico_City", "stadium": "Estadio Azteca",
            "city": "Cidade do México", "score_home": None, "score_away": None,
            "tv": "", "streaming": "",
        }
        desc = build_event_description(match)
        assert "📺" not in desc


class TestBuildEventLocation:
    def test_normal_venue(self, match_no_score):
        loc = build_event_location(match_no_score)
        assert loc == "MetLife Stadium, East Rutherford, EUA"

    def test_tbd_venue(self):
        match = {"stadium": "TBD", "city": "TBD"}
        loc = build_event_location(match)
        assert loc == "A definir"


class TestCreateCalendar:
    def test_calendar_properties(self):
        cal = create_calendar()
        assert cal["x-wr-calname"] == "Copa do Mundo FIFA 2026"
        assert cal["version"] == "2.0"
        assert cal["method"] == "PUBLISH"

    def test_calendar_refresh_interval(self):
        cal = create_calendar()
        ical_bytes = cal.to_ical()
        assert b"PT6H" in ical_bytes


class TestAddMatchEvent:
    def test_event_added_to_calendar(self, match_no_score):
        cal = create_calendar()
        add_match_event(cal, match_no_score)
        events = [c for c in cal.walk() if c.name == "VEVENT"]
        assert len(events) == 1

    def test_event_has_correct_uid(self, match_no_score):
        cal = create_calendar()
        add_match_event(cal, match_no_score)
        event = [c for c in cal.walk() if c.name == "VEVENT"][0]
        assert "fifawc2026-match007" in str(event["uid"])

    def test_event_duration_is_2_hours(self, match_no_score):
        cal = create_calendar()
        add_match_event(cal, match_no_score)
        event = [c for c in cal.walk() if c.name == "VEVENT"][0]
        start = event["dtstart"].dt
        end = event["dtend"].dt
        assert (end - start).total_seconds() == 7200

    def test_event_timezone_correct(self, match_no_score):
        cal = create_calendar()
        add_match_event(cal, match_no_score)
        event = [c for c in cal.walk() if c.name == "VEVENT"][0]
        start = event["dtstart"].dt
        assert str(start.tzinfo) == "America/New_York"


class TestMergeScores:
    def test_merge_applies_scores(self):
        matches = [
            {"match_number": 7, "home": "Brazil", "away": "Morocco"},
            {"match_number": 8, "home": "Haiti", "away": "Scotland"},
        ]
        scores = {"7": {"score_home": 2, "score_away": 0, "status": "finished"}}
        merged = merge_scores(matches, scores)
        assert merged[0]["score_home"] == 2
        assert merged[0]["score_away"] == 0
        assert merged[1]["score_home"] is None
        assert merged[1]["score_away"] is None

    def test_merge_does_not_mutate_original(self):
        matches = [{"match_number": 7, "home": "Brazil", "away": "Morocco"}]
        scores = {"7": {"score_home": 1, "score_away": 1, "status": "live"}}
        merge_scores(matches, scores)
        assert "score_home" not in matches[0]

    def test_empty_scores_leaves_all_none(self):
        matches = [
            {"match_number": 1, "home": "Mexico", "away": "South Africa"},
        ]
        merged = merge_scores(matches, {})
        assert merged[0]["score_home"] is None
        assert merged[0]["score_away"] is None
