"""Tests for fetch_matches.py — parsing, timezone mapping, and data integrity."""

import json
from pathlib import Path

import pytest

from fetch_matches import (
    normalize_stadium,
    parse_time_12h,
    classify_knockout_stage,
    VENUE_TIMEZONES,
    VENUE_CITIES_PT,
)


class TestParseTime12h:
    def test_pm_conversion(self):
        assert parse_time_12h("6:00 p.m.") == "18:00"
        assert parse_time_12h("1:00 p.m.") == "13:00"
        assert parse_time_12h("9:30 p.m.") == "21:30"

    def test_am_conversion(self):
        assert parse_time_12h("9:00 a.m.") == "09:00"
        assert parse_time_12h("11:30 a.m.") == "11:30"

    def test_noon(self):
        assert parse_time_12h("12:00 p.m.") == "12:00"

    def test_midnight(self):
        assert parse_time_12h("12:00 a.m.") == "00:00"

    def test_invalid_returns_tbd(self):
        assert parse_time_12h("TBD") == "TBD"
        assert parse_time_12h("") == "TBD"
        assert parse_time_12h("sometime") == "TBD"

    def test_alternate_format(self):
        assert parse_time_12h("3:00 pm") == "15:00"
        assert parse_time_12h("7:00 am") == "07:00"


class TestNormalizeStadium:
    def test_known_stadiums(self):
        assert normalize_stadium("MetLife Stadium") == "MetLife Stadium"
        assert normalize_stadium("Estadio Azteca") == "Estadio Azteca"
        assert normalize_stadium("BC Place") == "BC Place"

    def test_partial_match(self):
        assert normalize_stadium("MetLife Stadium, East Rutherford") == "MetLife Stadium"
        assert normalize_stadium("Hard Rock Stadium, Miami Gardens") == "Hard Rock Stadium"

    def test_unknown_stadium_returns_stripped(self):
        assert normalize_stadium("  Some New Arena  ") == "Some New Arena"


class TestClassifyKnockoutStage:
    def test_round_of_32(self):
        # Round of 32 = "16 Avos de Final" (16 matches, 28/06–03/07), first KO round
        assert classify_knockout_stage("2026-06-28") == "16 Avos de Final"
        assert classify_knockout_stage("2026-06-30") == "16 Avos de Final"
        assert classify_knockout_stage("2026-07-03") == "16 Avos de Final"

    def test_round_of_16(self):
        # Round of 16 = "Oitavas de Final" (8 matches, 04/07–07/07), after Round of 32
        assert classify_knockout_stage("2026-07-04") == "Oitavas de Final"
        assert classify_knockout_stage("2026-07-07") == "Oitavas de Final"

    def test_quarterfinals(self):
        assert classify_knockout_stage("2026-07-09") == "Quartas de Final"
        assert classify_knockout_stage("2026-07-11") == "Quartas de Final"

    def test_semifinals(self):
        assert classify_knockout_stage("2026-07-14") == "Semifinal"
        assert classify_knockout_stage("2026-07-15") == "Semifinal"

    def test_third_place(self):
        assert classify_knockout_stage("2026-07-18") == "Disputa de 3º Lugar"

    def test_final(self):
        assert classify_knockout_stage("2026-07-19") == "Final"

    def test_empty_date(self):
        assert classify_knockout_stage("") == "Mata-mata"
        assert classify_knockout_stage(None) == "Mata-mata"


class TestVenueMappings:
    def test_all_stadiums_have_timezone(self):
        for stadium in VENUE_TIMEZONES:
            assert VENUE_TIMEZONES[stadium], f"{stadium} has empty timezone"

    def test_all_stadiums_have_city(self):
        for stadium in VENUE_TIMEZONES:
            assert stadium in VENUE_CITIES_PT, f"{stadium} missing from VENUE_CITIES_PT"

    def test_timezone_values_are_valid(self):
        from zoneinfo import ZoneInfo
        for stadium, tz in VENUE_TIMEZONES.items():
            try:
                ZoneInfo(tz)
            except Exception:
                pytest.fail(f"{stadium} has invalid timezone: {tz}")


class TestMatchesJsonIntegrity:
    """Tests that run against the actual matches.json to catch data corruption."""

    @pytest.fixture
    def matches(self):
        path = Path(__file__).parent.parent / "matches.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_total_match_count(self, matches):
        assert len(matches) == 104

    def test_group_stage_has_72_matches(self, matches):
        groups = [m for m in matches if m["stage"].startswith("Grupo")]
        assert len(groups) == 72

    def test_knockout_has_32_matches(self, matches):
        knockout = [m for m in matches if not m["stage"].startswith("Grupo")]
        assert len(knockout) == 32

    def test_all_matches_have_required_fields(self, matches):
        required = ["match_number", "stage", "home", "away", "date", "time",
                    "timezone", "stadium", "city", "tv", "streaming"]
        for m in matches:
            for field in required:
                assert field in m, f"Match #{m.get('match_number', '?')} missing '{field}'"

    def test_all_dates_in_tournament_window(self, matches):
        for m in matches:
            date = m["date"]
            assert date >= "2026-06-11", f"Match #{m['match_number']} date {date} before tournament"
            assert date <= "2026-07-19", f"Match #{m['match_number']} date {date} after tournament"

    def test_all_times_are_valid(self, matches):
        import re
        for m in matches:
            assert re.match(r"\d{1,2}:\d{2}", m["time"]), \
                f"Match #{m['match_number']} has invalid time: {m['time']}"

    def test_no_duplicate_match_numbers(self, matches):
        numbers = [m["match_number"] for m in matches]
        assert len(numbers) == len(set(numbers))

    def test_brazil_has_3_group_matches(self, matches):
        brazil = [m for m in matches
                  if m["home"] == "Brazil" or m["away"] == "Brazil"]
        brazil_group = [m for m in brazil if m["stage"].startswith("Grupo")]
        assert len(brazil_group) == 3

    def test_each_group_has_6_matches(self, matches):
        from collections import Counter
        groups = Counter(m["stage"] for m in matches if m["stage"].startswith("Grupo"))
        for group, count in groups.items():
            assert count == 6, f"{group} has {count} matches, expected 6"

    def test_final_is_at_metlife(self, matches):
        final = [m for m in matches if m["stage"] == "Final"]
        assert len(final) == 1
        assert final[0]["stadium"] == "MetLife Stadium"
        assert final[0]["date"] == "2026-07-19"

    def test_all_stadiums_have_timezone_mapping(self, matches):
        for m in matches:
            assert m["timezone"] != "", f"Match #{m['match_number']} has no timezone"
