#!/usr/bin/env python3
"""
Fetch FIFA World Cup 2026 match data from Wikipedia and generate matches.json.

Sources:
- Group stage: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_A (through _L)
- Knockout stage: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage

Usage:
    python fetch_matches.py           # Fetch all 104 matches
    python fetch_matches.py --groups  # Fetch only group stage (72 matches)
    python fetch_matches.py --knockout # Fetch only knockout stage (32 matches)
"""

import argparse
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MATCHES_FILE = Path(__file__).parent / "matches.json"

GROUP_URLS = {
    letter: f"https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_Group_{letter}"
    for letter in "ABCDEFGHIJKL"
}
KNOCKOUT_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage"

VENUE_TIMEZONES = {
    "Estadio Azteca": "America/Mexico_City",
    "Estadio BBVA": "America/Mexico_City",
    "Estadio Akron": "America/Mexico_City",
    "MetLife Stadium": "America/New_York",
    "Hard Rock Stadium": "America/New_York",
    "Lincoln Financial Field": "America/New_York",
    "Mercedes-Benz Stadium": "America/New_York",
    "AT&T Stadium": "America/Chicago",
    "NRG Stadium": "America/Chicago",
    "Arrowhead Stadium": "America/Chicago",
    "Lumen Field": "America/Los_Angeles",
    "Levi's Stadium": "America/Los_Angeles",
    "SoFi Stadium": "America/Los_Angeles",
    "Rose Bowl": "America/Los_Angeles",
    "BC Place": "America/Vancouver",
    "BMO Field": "America/Toronto",
    "Gillette Stadium": "America/New_York",
}

VENUE_CITIES_PT = {
    "Estadio Azteca": "Cidade do México, México",
    "Estadio BBVA": "Monterrey, México",
    "Estadio Akron": "Guadalajara, México",
    "MetLife Stadium": "East Rutherford, EUA",
    "Hard Rock Stadium": "Miami, EUA",
    "Lincoln Financial Field": "Filadélfia, EUA",
    "Mercedes-Benz Stadium": "Atlanta, EUA",
    "AT&T Stadium": "Arlington, EUA",
    "NRG Stadium": "Houston, EUA",
    "Arrowhead Stadium": "Kansas City, EUA",
    "Lumen Field": "Seattle, EUA",
    "Levi's Stadium": "Santa Clara, EUA",
    "SoFi Stadium": "Inglewood, EUA",
    "Rose Bowl": "Pasadena, EUA",
    "BC Place": "Vancouver, Canadá",
    "BMO Field": "Toronto, Canadá",
    "Gillette Stadium": "Foxborough, EUA",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def normalize_stadium(raw: str) -> str:
    """Match raw venue text to a known stadium name."""
    for known in VENUE_TIMEZONES:
        if known.lower() in raw.lower():
            return known
    return raw.strip()


def parse_time_12h(time_str: str) -> str:
    """Convert '6:00 p.m.' or '1:00 p.m.' to 24h format '18:00'."""
    match = re.search(r"(\d{1,2}):(\d{2})\s*(a\.m\.|p\.m\.|am|pm)", time_str.lower())
    if not match:
        return "TBD"
    hour = int(match.group(1))
    minute = match.group(2)
    period = match.group(3).replace(".", "")
    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute}"


def parse_footballbox(box, stage: str) -> dict | None:
    """Parse a single footballbox div into a match dict."""
    match = {"stage": stage, "tv": "", "streaming": "", "score_home": None, "score_away": None}

    # Date
    fdate = box.find("div", class_="fdate")
    if fdate:
        bday = fdate.find("span", class_="bday")
        if bday:
            match["date"] = bday.get_text(strip=True)
        else:
            date_text = fdate.get_text(strip=True)
            date_match = re.search(r"(\w+)\s+(\d{1,2}),?\s+(\d{4})", date_text)
            if date_match:
                months = {
                    "January": "01", "February": "02", "March": "03",
                    "April": "04", "May": "05", "June": "06",
                    "July": "07", "August": "08", "September": "09",
                    "October": "10", "November": "11", "December": "12"
                }
                month = months.get(date_match.group(1), "01")
                day = int(date_match.group(2))
                year = date_match.group(3)
                match["date"] = f"{year}-{month}-{day:02d}"

    # Time
    ftime = box.find("div", class_="ftime")
    if ftime:
        match["time"] = parse_time_12h(ftime.get_text(strip=True))

    # Home team
    fhome = box.find("th", class_="fhome")
    if fhome:
        link = fhome.find("a")
        if link:
            match["home"] = link.get_text(strip=True)
        else:
            match["home"] = fhome.get_text(strip=True)

    # Away team
    faway = box.find("th", class_="faway")
    if faway:
        link = faway.find("a")
        if link:
            match["away"] = link.get_text(strip=True)
        else:
            match["away"] = faway.get_text(strip=True)

    # Score / Match number
    fscore = box.find("th", class_="fscore")
    if fscore:
        score_text = fscore.get_text(strip=True)
        score_match = re.search(r"(\d+)\s*[–\-]\s*(\d+)", score_text)
        if score_match:
            match["score_home"] = int(score_match.group(1))
            match["score_away"] = int(score_match.group(2))
        # Extract match number
        num_match = re.search(r"Match\s+(\d+)", score_text)
        if num_match:
            match["match_number"] = int(num_match.group(1))
        else:
            match["match_number"] = 0

    # Venue
    fright = box.find("div", class_="fright")
    if fright:
        venue_text = fright.get_text(strip=True)
        # Remove any trailing referee info
        venue_text = venue_text.split("Referee:")[0].strip()
        stadium = normalize_stadium(venue_text)
        match["stadium"] = stadium
        match["city"] = VENUE_CITIES_PT.get(stadium, venue_text)
        match["timezone"] = VENUE_TIMEZONES.get(stadium, "America/New_York")
    else:
        match["stadium"] = "TBD"
        match["city"] = "TBD"
        match["timezone"] = "America/New_York"

    if "home" in match and "away" in match:
        return match
    return None


def fetch_group_matches(group_letter: str) -> list[dict]:
    """Fetch all matches for a specific group."""
    url = GROUP_URLS[group_letter]
    soup = fetch_page(url)
    stage = f"Grupo {group_letter}"

    boxes = soup.find_all("div", class_="footballbox")
    matches = []
    for box in boxes:
        match = parse_footballbox(box, stage)
        if match:
            matches.append(match)
    return matches


def classify_knockout_stage(date_str: str) -> str:
    """Determine knockout stage from match date."""
    if not date_str:
        return "Mata-mata"
    day = int(date_str[8:10])
    month = int(date_str[5:7])
    # 48-team format: Round of 32 (16 avos, 28/06–03/07) comes BEFORE
    # Round of 16 (oitavas, 04/07–07/07). Do not swap these.
    if month == 6:
        return "16 Avos de Final"
    if month == 7:
        if day <= 3:
            return "16 Avos de Final"
        if day <= 7:
            return "Oitavas de Final"
        if day <= 11:
            return "Quartas de Final"
        if day <= 15:
            return "Semifinal"
        if day == 18:
            return "Disputa de 3º Lugar"
        if day == 19:
            return "Final"
    return "Mata-mata"


def fetch_knockout_matches() -> list[dict]:
    """Fetch all knockout stage matches from the bracket table."""
    soup = fetch_page(KNOCKOUT_URL)

    boxes = soup.find_all("div", class_="footballbox")
    matches = []

    for box in boxes:
        match = parse_footballbox(box, "Mata-mata")
        if match:
            match["stage"] = classify_knockout_stage(match.get("date", ""))
            matches.append(match)

    return matches


def main():
    parser = argparse.ArgumentParser(description="Fetch FIFA WC 2026 match data from Wikipedia")
    parser.add_argument("--groups", action="store_true", help="Fetch only group stage")
    parser.add_argument("--knockout", action="store_true", help="Fetch only knockout stage")
    args = parser.parse_args()

    fetch_groups = not args.knockout or args.groups
    fetch_ko = not args.groups or args.knockout
    if not args.groups and not args.knockout:
        fetch_groups = True
        fetch_ko = True

    all_matches = []

    if fetch_groups:
        print("Fetching group stage matches...")
        for letter in "ABCDEFGHIJKL":
            print(f"  Group {letter}...", end=" ")
            try:
                group_matches = fetch_group_matches(letter)
                print(f"{len(group_matches)} matches")
                all_matches.extend(group_matches)
            except Exception as e:
                print(f"ERROR: {e}")

    if fetch_ko:
        print("Fetching knockout stage matches...")
        try:
            ko_matches = fetch_knockout_matches()
            print(f"  Found {len(ko_matches)} matches")
            all_matches.extend(ko_matches)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Sort by date and time
    all_matches.sort(key=lambda m: (m.get("date", "9999"), m.get("time", "99:99")))

    # Assign sequential match numbers if not already set from Wikipedia
    for i, match in enumerate(all_matches, start=1):
        if match.get("match_number", 0) == 0:
            match["match_number"] = i

    MATCHES_FILE.write_text(
        json.dumps(all_matches, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\nTotal: {len(all_matches)} matches saved to {MATCHES_FILE}")


if __name__ == "__main__":
    main()
