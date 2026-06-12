"""Tests for score_sources/matching.py — UTC-instant match resolution.

The headline case: match #2 (Korea vs Czech) has local date 2026-06-11 but
UTC date 2026-06-12. The old date-string matcher failed for all 36 such
matches; this matcher must resolve it correctly.
"""

from datetime import datetime, timezone

from score_sources.matching import match_utc_instant, resolve_match_number


# Real matches.json entries (local date/time/timezone).
MATCHES = [
    {"match_number": 1, "home": "Mexico", "away": "South Africa",
     "date": "2026-06-11", "time": "13:00", "timezone": "America/Mexico_City"},
    {"match_number": 2, "home": "South Korea", "away": "Czech Republic",
     "date": "2026-06-11", "time": "20:00", "timezone": "America/Mexico_City"},
    {"match_number": 7, "home": "Brazil", "away": "Morocco",
     "date": "2026-06-13", "time": "18:00", "timezone": "America/New_York"},
]


class TestMatchUtcInstant:
    def test_evening_match_rolls_to_next_utc_day(self):
        # 20:00 Mexico City (UTC-6) = 02:00 UTC the next day.
        m = MATCHES[1]
        assert match_utc_instant(m) == datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)

    def test_afternoon_match_same_utc_day(self):
        # 13:00 Mexico City = 19:00 UTC same day.
        assert match_utc_instant(MATCHES[0]) == datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc)

    def test_missing_fields_returns_none(self):
        assert match_utc_instant({"date": "", "time": "", "timezone": ""}) is None


class TestResolveMatchNumber:
    def test_resolves_match_crossing_utc_midnight(self):
        # The regression case: ESPN reports this kickoff as 2026-06-12T02:00Z.
        kickoff = datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)
        assert resolve_match_number(MATCHES, "South Korea", "Czech Republic", kickoff) == 2

    def test_team_order_is_ignored(self):
        kickoff = datetime(2026, 6, 12, 2, 0, tzinfo=timezone.utc)
        # away/home swapped relative to matches.json
        assert resolve_match_number(MATCHES, "Czech Republic", "South Korea", kickoff) == 2

    def test_resolves_afternoon_match(self):
        kickoff = datetime(2026, 6, 11, 19, 0, tzinfo=timezone.utc)
        assert resolve_match_number(MATCHES, "Mexico", "South Africa", kickoff) == 1

    def test_wrong_instant_does_not_match(self):
        # Right teams, but a kickoff a full day off → outside the window.
        kickoff = datetime(2026, 6, 13, 2, 0, tzinfo=timezone.utc)
        assert resolve_match_number(MATCHES, "South Korea", "Czech Republic", kickoff) is None

    def test_unknown_pair_returns_none(self):
        kickoff = datetime(2026, 6, 13, 22, 0, tzinfo=timezone.utc)
        assert resolve_match_number(MATCHES, "Spain", "Italy", kickoff) is None
