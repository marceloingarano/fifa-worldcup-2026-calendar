#!/usr/bin/env python3
"""
Update knockout stage teams in matches.json as the tournament progresses.

Replaces placeholders like "Winner Group C" with actual team names once
group stage results are determined.

Sources (in priority order):
1. OpenLigaDB — if knockout fixtures have real teams assigned
2. Wikipedia — fallback re-scrape of knockout stage page

Usage:
    python update_knockout.py          # Auto: try OpenLigaDB, fallback to Wikipedia
    python update_knockout.py --api    # Only OpenLigaDB
    python update_knockout.py --wiki   # Only Wikipedia
"""

import argparse
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from fetch_matches import (
    parse_footballbox,
    classify_knockout_stage,
    VENUE_TIMEZONES,
    VENUE_CITIES_PT,
    normalize_stadium,
)
from score_sources.openligadb import TEAM_SHORT_TO_NAME

MATCHES_FILE = Path(__file__).parent / "matches.json"
API_BASE_URL = "https://api.openligadb.de"
LEAGUE_SHORTCUT = "wm26"
SEASON = 2026
WIKIPEDIA_KNOCKOUT_URL = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

KNOCKOUT_MATCHDAYS = {
    # 48-team format: matchday 4 = Round of 32 (16 avos), matchday 5 =
    # Round of 16 (oitavas). Mirrors update_scores.py MATCHDAYS
    # (Sechzehntelfinale=4, Achtelfinale=5). Do not swap these.
    4: "16 Avos de Final",
    5: "Oitavas de Final",
    6: "Quartas de Final",
    7: "Semifinal",
    8: "Final",
}


def load_matches() -> list[dict]:
    return json.loads(MATCHES_FILE.read_text(encoding="utf-8"))


def save_matches(matches: list[dict]) -> None:
    MATCHES_FILE.write_text(
        json.dumps(matches, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def is_placeholder(team_name: str) -> bool:
    """Check if team name is a placeholder (not a real team)."""
    placeholders = ["Winner", "Loser", "Runner-up", "3rd Group", "TBD"]
    return any(team_name.startswith(p) for p in placeholders)


def _convert_utc_to_local_time(utc_time: str, timezone: str) -> str:
    """Convert HH:MM UTC to local time in the given timezone."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if not utc_time or not timezone:
        return ""
    try:
        dt = datetime(2026, 6, 15, int(utc_time[:2]), int(utc_time[3:5]), tzinfo=ZoneInfo("UTC"))
        local = dt.astimezone(ZoneInfo(timezone))
        return f"{local.hour:02d}:{local.minute:02d}"
    except Exception:
        return ""


def _find_knockout_match(matches: list[dict], match_date: str, match_time_utc: str) -> dict | None:
    """Find a knockout match by date + time (UTC converted to local)."""
    candidates = []
    for m in matches:
        if m["date"] != match_date:
            continue
        if m["stage"].startswith("Grupo"):
            continue
        if not (is_placeholder(m["home"]) or is_placeholder(m["away"])):
            continue
        candidates.append(m)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Multiple matches on same day — match by time
    for m in candidates:
        local_time = _convert_utc_to_local_time(match_time_utc, m["timezone"])
        if local_time == m["time"]:
            return m

    return None


def _find_knockout_match_by_local_time(matches: list[dict], match_date: str, local_time: str) -> dict | None:
    """Find a knockout match by date + local time (Wikipedia already provides local time)."""
    candidates = []
    for m in matches:
        if m["date"] != match_date:
            continue
        if m["stage"].startswith("Grupo"):
            continue
        if not (is_placeholder(m["home"]) or is_placeholder(m["away"])):
            continue
        candidates.append(m)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Multiple matches on same day — match by local time
    for m in candidates:
        if m["time"] == local_time:
            return m

    return None


def has_knockout_placeholders(matches: list[dict]) -> bool:
    """Check if there are still placeholder teams in knockout matches."""
    for m in matches:
        if m["stage"].startswith("Grupo"):
            continue
        if is_placeholder(m["home"]) or is_placeholder(m["away"]):
            return True
    return False


def update_from_openligadb(matches: list[dict]) -> int:
    """Try to update knockout teams from OpenLigaDB. Returns count of updates."""
    updated = 0

    for matchday, stage in KNOCKOUT_MATCHDAYS.items():
        url = f"{API_BASE_URL}/getmatchdata/{LEAGUE_SHORTCUT}/{SEASON}/{matchday}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            api_data = resp.json()
        except requests.RequestException as e:
            print(f"  Matchday {matchday}: ERROR - {e}")
            continue

        if not api_data:
            print(f"  Matchday {matchday} ({stage}): no fixtures yet")
            continue

        print(f"  Matchday {matchday} ({stage}): {len(api_data)} fixtures")

        for api_match in api_data:
            home_short = api_match["team1"].get("shortName", "")
            away_short = api_match["team2"].get("shortName", "")
            home_name = TEAM_SHORT_TO_NAME.get(home_short, "")
            away_name = TEAM_SHORT_TO_NAME.get(away_short, "")

            if not home_name or not away_name:
                continue

            match_date = api_match.get("matchDateTimeUTC", "")[:10]
            match_time_utc = api_match.get("matchDateTimeUTC", "")[11:16]

            target = _find_knockout_match(matches, match_date, match_time_utc)
            if target is None:
                continue

            if is_placeholder(target["home"]) and home_name:
                print(f"    #{target['match_number']}: {target['home']} → {home_name}")
                target["home"] = home_name
                updated += 1
            if is_placeholder(target["away"]) and away_name:
                print(f"    #{target['match_number']}: {target['away']} → {away_name}")
                target["away"] = away_name
                updated += 1

    return updated


def update_from_wikipedia(matches: list[dict]) -> int:
    """Fallback: re-scrape Wikipedia knockout page for real team names."""
    print("  Fetching Wikipedia knockout page...")
    try:
        resp = requests.get(WIKIPEDIA_KNOCKOUT_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as e:
        print(f"  ERROR: {e}")
        return 0

    boxes = soup.find_all("div", class_="footballbox")
    if not boxes:
        print("  No footballboxes found")
        return 0

    updated = 0
    wiki_matches = []
    for box in boxes:
        wm = parse_footballbox(box, "knockout")
        if wm:
            wm["stage"] = classify_knockout_stage(wm.get("date", ""))
            wiki_matches.append(wm)

    print(f"  Found {len(wiki_matches)} knockout matches on Wikipedia")

    for wm in wiki_matches:
        wiki_home = wm.get("home", "")
        wiki_away = wm.get("away", "")
        wiki_date = wm.get("date", "")

        if is_placeholder(wiki_home) and is_placeholder(wiki_away):
            continue

        wiki_time = wm.get("time", "")
        target = _find_knockout_match_by_local_time(matches, wiki_date, wiki_time)
        if target is None:
            continue

        if is_placeholder(target["home"]) and not is_placeholder(wiki_home):
            print(f"    #{target['match_number']}: {target['home']} → {wiki_home}")
            target["home"] = wiki_home
            updated += 1
        if is_placeholder(target["away"]) and not is_placeholder(wiki_away):
            print(f"    #{target['match_number']}: {target['away']} → {wiki_away}")
            target["away"] = wiki_away
            updated += 1

        if target["stadium"] == "TBD" and wm.get("stadium"):
            stadium = normalize_stadium(wm["stadium"])
            target["stadium"] = stadium
            target["city"] = VENUE_CITIES_PT.get(stadium, wm.get("city", ""))
            target["timezone"] = VENUE_TIMEZONES.get(stadium, "America/New_York")

    return updated


def main():
    parser = argparse.ArgumentParser(description="Update knockout teams in matches.json")
    parser.add_argument("--api", action="store_true", help="Only use OpenLigaDB")
    parser.add_argument("--wiki", action="store_true", help="Only use Wikipedia")
    args = parser.parse_args()

    matches = load_matches()

    if not has_knockout_placeholders(matches):
        print("All knockout teams already resolved. Nothing to update.")
        return

    updated = 0

    if args.wiki:
        print("Updating knockout teams from Wikipedia...")
        updated = update_from_wikipedia(matches)
    elif args.api:
        print("Updating knockout teams from OpenLigaDB...")
        updated = update_from_openligadb(matches)
    else:
        # Auto: try API first, fallback to Wikipedia
        print("Updating knockout teams from OpenLigaDB...")
        updated = update_from_openligadb(matches)
        if has_knockout_placeholders(matches):
            print("\nStill has placeholders. Trying Wikipedia fallback...")
            updated += update_from_wikipedia(matches)

    if updated > 0:
        save_matches(matches)
        print(f"\nUpdated {updated} team names. Run generate_calendar.py to regenerate .ics.")
    else:
        print("\nNo updates available yet.")


if __name__ == "__main__":
    main()
