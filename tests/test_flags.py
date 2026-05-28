"""Tests for flags.py — emoji flags, PT-BR names, and timezone abbreviations."""

import pytest
from flags import get_flag, get_name_pt, get_tz_abbr, FLAGS, NAMES_PT_BR, TIMEZONE_ABBR


class TestGetFlag:
    def test_known_team_returns_flag(self):
        assert get_flag("Brazil") == "\U0001f1e7\U0001f1f7"
        assert get_flag("Argentina") == "\U0001f1e6\U0001f1f7"

    def test_unknown_team_returns_football(self):
        assert get_flag("Winner Match 101") == "⚽"
        assert get_flag("NonExistentTeam") == "⚽"

    def test_tbd_returns_question_mark(self):
        assert get_flag("TBD") == "❓"

    def test_all_group_stage_teams_have_flags(self):
        group_teams = [
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
        ]
        for team in group_teams:
            flag = get_flag(team)
            assert flag != "⚽", f"{team} is missing a flag emoji"


class TestGetNamePt:
    def test_known_team_returns_portuguese_name(self):
        assert get_name_pt("Brazil") == "BRASIL"
        assert get_name_pt("Germany") == "Alemanha"
        assert get_name_pt("United States") == "Estados Unidos"
        assert get_name_pt("Ivory Coast") == "Costa do Marfim"

    def test_unknown_team_returns_original_name(self):
        assert get_name_pt("Winner Match 101") == "Winner Match 101"
        assert get_name_pt("Runner-up Group A") == "Runner-up Group A"

    def test_tbd_returns_a_definir(self):
        assert get_name_pt("TBD") == "A definir"

    def test_all_group_stage_teams_are_in_dictionary(self):
        group_teams = [
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
        ]
        for team in group_teams:
            assert team in NAMES_PT_BR, f"{team} is missing from NAMES_PT_BR dictionary"


class TestGetTzAbbr:
    def test_known_timezone(self):
        assert get_tz_abbr("America/New_York") == "ET"
        assert get_tz_abbr("America/Mexico_City") == "CST"
        assert get_tz_abbr("America/Los_Angeles") == "PT"

    def test_unknown_timezone_returns_raw(self):
        assert get_tz_abbr("Europe/London") == "Europe/London"


class TestDataConsistency:
    def test_flags_and_names_have_same_keys(self):
        """Every team in FLAGS should have a PT-BR name and vice versa."""
        flags_keys = set(FLAGS.keys())
        names_keys = set(NAMES_PT_BR.keys())
        missing_names = flags_keys - names_keys
        missing_flags = names_keys - flags_keys
        assert not missing_names, f"Teams in FLAGS but not NAMES_PT_BR: {missing_names}"
        assert not missing_flags, f"Teams in NAMES_PT_BR but not FLAGS: {missing_flags}"
