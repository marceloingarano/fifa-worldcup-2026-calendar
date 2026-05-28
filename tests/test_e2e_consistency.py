"""
End-to-end consistency test.

Picks random matches from the generated .ics file and validates them
against Wikipedia as the external source of truth.

Usage:
    pytest tests/test_e2e_consistency.py -v              # Run with default 5 random matches
    pytest tests/test_e2e_consistency.py -v -k e2e       # Same
    E2E_SAMPLE_SIZE=10 pytest tests/test_e2e_consistency.py  # Test 10 random matches

Requires network access (fetches Wikipedia pages).
Mark with @pytest.mark.e2e so it can be excluded from fast CI runs.
"""

import json
import os
import random
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import requests
from bs4 import BeautifulSoup
from icalendar import Calendar

PROJECT_ROOT = Path(__file__).parent.parent
ICS_FILE = PROJECT_ROOT / "docs" / "fifa-worldcup-2026.ics"
MATCHES_FILE = PROJECT_ROOT / "matches.json"

SAMPLE_SIZE = int(os.environ.get("E2E_SAMPLE_SIZE", "5"))

WIKIPEDIA_GROUP_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_{letter}"
WIKIPEDIA_KNOCKOUT_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def fetch_wikipedia_group(letter: str) -> list[dict]:
    """Fetch match data from a Wikipedia group page."""
    url = WIKIPEDIA_GROUP_URL.format(letter=letter)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    matches = []
    for box in soup.find_all("div", class_="footballbox"):
        match = parse_footballbox(box)
        if match:
            matches.append(match)
    return matches


def fetch_wikipedia_knockout() -> list[dict]:
    """Fetch match data from Wikipedia knockout page."""
    resp = requests.get(WIKIPEDIA_KNOCKOUT_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    matches = []
    for box in soup.find_all("div", class_="footballbox"):
        match = parse_footballbox(box)
        if match:
            matches.append(match)
    return matches


def parse_footballbox(box) -> dict | None:
    """Parse a single footballbox into a dict with home, away, date, time, venue, score."""
    match = {}

    # Date
    fdate = box.find("div", class_="fdate")
    if fdate:
        bday = fdate.find("span", class_="bday")
        if bday:
            match["date"] = bday.get_text(strip=True)

    # Time
    ftime = box.find("div", class_="ftime")
    if ftime:
        time_text = ftime.get_text(strip=True).lower()
        time_match = re.search(r"(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.|am|pm)", time_text)
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2)
            period = time_match.group(3).replace(".", "")
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            match["time"] = f"{hour:02d}:{minute}"

    # Home team
    fhome = box.find("th", class_="fhome")
    if fhome:
        link = fhome.find("a")
        match["home"] = link.get_text(strip=True) if link else fhome.get_text(strip=True)

    # Away team
    faway = box.find("th", class_="faway")
    if faway:
        link = faway.find("a")
        match["away"] = link.get_text(strip=True) if link else faway.get_text(strip=True)

    # Score
    fscore = box.find("th", class_="fscore")
    if fscore:
        score_text = fscore.get_text(strip=True)
        score_match = re.search(r"(\d+)\s*[–\-]\s*(\d+)", score_text)
        if score_match:
            match["score_home"] = int(score_match.group(1))
            match["score_away"] = int(score_match.group(2))

    # Venue
    fright = box.find("div", class_="fright")
    if fright:
        venue_text = fright.get_text(strip=True).split("Referee:")[0].strip()
        match["venue"] = venue_text

    if "home" in match and "away" in match and "date" in match:
        return match
    return None


def parse_ics_events() -> list[dict]:
    """Parse all events from the generated .ics file."""
    cal = Calendar.from_ical(ICS_FILE.read_bytes())
    events = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        event = {
            "summary": str(component.get("summary", "")),
            "location": str(component.get("location", "")),
            "description": str(component.get("description", "")),
            "dtstart": component.get("dtstart").dt if component.get("dtstart") else None,
            "uid": str(component.get("uid", "")),
        }
        events.append(event)
    return events


def get_match_from_ics(events: list[dict], match_number: int) -> dict | None:
    """Find a specific match in the .ics events by match number in UID."""
    uid_pattern = f"fifawc2026-match{match_number:03d}"
    for event in events:
        if uid_pattern in event["uid"]:
            return event
    return None


def find_wikipedia_match(wiki_matches: list[dict], our_match: dict) -> dict | None:
    """Find matching Wikipedia entry by date and team names."""
    our_date = our_match.get("date", "")
    our_home = our_match.get("home", "")
    our_away = our_match.get("away", "")

    for wm in wiki_matches:
        if wm.get("date") != our_date:
            continue
        wiki_home = wm.get("home", "")
        wiki_away = wm.get("away", "")
        if (wiki_home == our_home and wiki_away == our_away) or \
           (wiki_home == our_away and wiki_away == our_home):
            return wm
    return None


@pytest.fixture(scope="module")
def ics_events():
    """Load .ics events once for all tests."""
    assert ICS_FILE.exists(), f".ics file not found at {ICS_FILE}"
    return parse_ics_events()


@pytest.fixture(scope="module")
def matches_data():
    """Load matches.json once for all tests."""
    return json.loads(MATCHES_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def random_group_matches(matches_data):
    """Pick random group stage matches for E2E validation."""
    group_matches = [m for m in matches_data if m["stage"].startswith("Grupo")]
    return random.sample(group_matches, min(SAMPLE_SIZE, len(group_matches)))


@pytest.fixture(scope="module")
def wikipedia_cache():
    """Cache Wikipedia fetches to minimize requests."""
    return {}


def get_wikipedia_matches_for_group(group_letter: str, cache: dict) -> list[dict]:
    """Fetch Wikipedia group data with caching."""
    if group_letter not in cache:
        cache[group_letter] = fetch_wikipedia_group(group_letter)
    return cache[group_letter]


@pytest.mark.e2e
class TestE2EConsistency:
    """
    End-to-end test: validates random .ics events against Wikipedia.

    Checks:
    - Date matches
    - Time matches
    - Teams are correct
    - Venue/location is consistent
    - Score is consistent (if available on both sides)
    """

    def test_ics_has_104_events(self, ics_events):
        assert len(ics_events) == 104, f"Expected 104 events, got {len(ics_events)}"

    def test_random_matches_date_consistency(self, random_group_matches, ics_events,
                                              matches_data, wikipedia_cache):
        """Verify dates match between .ics and Wikipedia for random matches."""
        errors = []

        for match in random_group_matches:
            group_letter = match["stage"].replace("Grupo ", "")
            wiki_matches = get_wikipedia_matches_for_group(group_letter, wikipedia_cache)
            wiki_match = find_wikipedia_match(wiki_matches, match)

            if wiki_match is None:
                errors.append(f"Match #{match['match_number']} ({match['home']} vs {match['away']}): "
                              f"not found on Wikipedia")
                continue

            # Compare date
            if match["date"] != wiki_match.get("date"):
                errors.append(f"Match #{match['match_number']}: "
                              f"date mismatch — ours={match['date']}, wiki={wiki_match.get('date')}")

        assert not errors, "Date inconsistencies found:\n" + "\n".join(errors)

    def test_random_matches_time_consistency(self, random_group_matches, ics_events,
                                             matches_data, wikipedia_cache):
        """Verify kick-off times match between .ics and Wikipedia."""
        errors = []

        for match in random_group_matches:
            group_letter = match["stage"].replace("Grupo ", "")
            wiki_matches = get_wikipedia_matches_for_group(group_letter, wikipedia_cache)
            wiki_match = find_wikipedia_match(wiki_matches, match)

            if wiki_match is None:
                continue

            our_time = match.get("time", "")
            wiki_time = wiki_match.get("time", "")

            if our_time and wiki_time and our_time != wiki_time:
                errors.append(f"Match #{match['match_number']} ({match['home']} vs {match['away']}): "
                              f"time mismatch — ours={our_time}, wiki={wiki_time}")

        assert not errors, "Time inconsistencies found:\n" + "\n".join(errors)

    def test_random_matches_venue_consistency(self, random_group_matches, ics_events,
                                              matches_data, wikipedia_cache):
        """Verify venues are consistent between .ics and Wikipedia."""
        errors = []

        for match in random_group_matches:
            group_letter = match["stage"].replace("Grupo ", "")
            wiki_matches = get_wikipedia_matches_for_group(group_letter, wikipedia_cache)
            wiki_match = find_wikipedia_match(wiki_matches, match)

            if wiki_match is None:
                continue

            wiki_venue = wiki_match.get("venue", "")
            our_stadium = match.get("stadium", "")

            # Check that our stadium name appears in wiki venue text
            if our_stadium and wiki_venue and our_stadium.lower() not in wiki_venue.lower():
                errors.append(f"Match #{match['match_number']} ({match['home']} vs {match['away']}): "
                              f"venue mismatch — ours={our_stadium}, wiki={wiki_venue}")

        assert not errors, "Venue inconsistencies found:\n" + "\n".join(errors)

    def test_random_matches_teams_in_ics(self, random_group_matches, ics_events):
        """Verify team names appear in the .ics event summary."""
        from flags import get_name_pt
        errors = []

        for match in random_group_matches:
            ics_event = get_match_from_ics(ics_events, match["match_number"])
            if ics_event is None:
                errors.append(f"Match #{match['match_number']}: not found in .ics")
                continue

            summary = ics_event["summary"]
            home_pt = get_name_pt(match["home"])
            away_pt = get_name_pt(match["away"])

            if home_pt not in summary:
                errors.append(f"Match #{match['match_number']}: '{home_pt}' not in title '{summary}'")
            if away_pt not in summary:
                errors.append(f"Match #{match['match_number']}: '{away_pt}' not in title '{summary}'")

        assert not errors, "Team name issues in .ics:\n" + "\n".join(errors)

    def test_random_matches_score_consistency(self, random_group_matches, ics_events,
                                              wikipedia_cache):
        """If Wikipedia has a score, verify it matches our .ics."""
        from flags import get_name_pt
        errors = []

        for match in random_group_matches:
            group_letter = match["stage"].replace("Grupo ", "")
            wiki_matches = get_wikipedia_matches_for_group(group_letter, wikipedia_cache)
            wiki_match = find_wikipedia_match(wiki_matches, match)

            if wiki_match is None:
                continue

            wiki_score_home = wiki_match.get("score_home")
            wiki_score_away = wiki_match.get("score_away")

            if wiki_score_home is None:
                continue  # Match not played yet

            # Check if our .ics has the score in the title
            ics_event = get_match_from_ics(ics_events, match["match_number"])
            if ics_event is None:
                continue

            summary = ics_event["summary"]
            expected_score = f"{wiki_score_home} x {wiki_score_away}"

            if expected_score not in summary:
                # Maybe we don't have the score yet (not updated) — warn but don't fail
                # Only fail if we have a DIFFERENT score
                score_pattern = re.search(r"(\d+) x (\d+)", summary)
                if score_pattern:
                    our_score = f"{score_pattern.group(1)} x {score_pattern.group(2)}"
                    if our_score != expected_score:
                        errors.append(
                            f"Match #{match['match_number']} ({match['home']} vs {match['away']}): "
                            f"score mismatch — ours={our_score}, wiki={expected_score}")

        assert not errors, "Score inconsistencies found:\n" + "\n".join(errors)

    def test_ics_location_field_populated(self, ics_events):
        """Verify all group stage events have a non-empty location."""
        empty_locations = []
        for event in ics_events:
            if "A definir" not in event["location"] and not event["location"].strip():
                empty_locations.append(event["uid"])

        assert not empty_locations, \
            f"{len(empty_locations)} events have empty location field"

    def test_ics_description_has_required_fields(self, ics_events):
        """Verify all events have stage and match number in description."""
        errors = []
        for event in ics_events:
            desc = event["description"]
            if "FIFA World Cup 2026" not in desc:
                errors.append(f"{event['uid']}: missing 'FIFA World Cup 2026' in description")
            if "Jogo #" not in desc:
                errors.append(f"{event['uid']}: missing 'Jogo #' in description")

        assert not errors, "Description issues:\n" + "\n".join(errors)
