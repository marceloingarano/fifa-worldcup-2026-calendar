#!/usr/bin/env python3
"""
Update scores.json from API-Football (api-sports.io).

Modes:
    python update_scores.py --live         # Fetch live + recently finished matches
    python update_scores.py --final        # Final consolidation (all finished matches)
    python update_scores.py --auto         # Smart mode: calls every 10min during match windows
    python update_scores.py --manual 7 2 0 # Manually set: match 7, home 2, away 0
    python update_scores.py --status       # Show API usage and rate limit status

Rate limiting:
    - Hard cap: 85 requests/day (leaves 15 buffer from 100 limit)
    - Tracks usage in .api_usage.json
    - Resets daily at UTC midnight
"""

import argparse
import json
import sys
from datetime import datetime, date
from pathlib import Path

import requests

SCORES_FILE = Path(__file__).parent / "scores.json"
MATCHES_FILE = Path(__file__).parent / "matches.json"
USAGE_FILE = Path(__file__).parent / ".api_usage.json"

API_BASE_URL = "https://v3.football.api-sports.io"
API_KEY_FILE = Path(__file__).parent / ".api_key"

LEAGUE_ID = 1
SEASON = 2026
DAILY_LIMIT = 85


def get_api_key() -> str:
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()
    import os
    key = os.environ.get("API_FOOTBALL_KEY", "")
    if not key:
        print("ERROR: No API key found.")
        print(f"  Create {API_KEY_FILE} with your key, or set API_FOOTBALL_KEY env var.")
        print("  Get a free key at: https://www.api-football.com/")
        sys.exit(1)
    return key


def load_usage() -> dict:
    if USAGE_FILE.exists():
        data = json.loads(USAGE_FILE.read_text())
        if data.get("date") == str(date.today()):
            return data
    return {"date": str(date.today()), "count": 0, "calls": []}


def save_usage(usage: dict) -> None:
    USAGE_FILE.write_text(json.dumps(usage, indent=2))


def check_rate_limit(usage: dict) -> bool:
    if usage["count"] >= DAILY_LIMIT:
        print(f"RATE LIMIT: {usage['count']}/{DAILY_LIMIT} requests used today. Blocked.")
        return False
    return True


def record_call(usage: dict, endpoint: str) -> dict:
    usage["count"] += 1
    usage["calls"].append({
        "time": datetime.now().isoformat(),
        "endpoint": endpoint,
    })
    save_usage(usage)
    return usage


def api_call(endpoint: str, params: dict, usage: dict) -> dict | None:
    if not check_rate_limit(usage):
        return None

    api_key = get_api_key()
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"x-apisports-key": api_key}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        record_call(usage, f"{endpoint}?{json.dumps(params)}")
        data = resp.json()

        if data.get("errors"):
            print(f"API error: {data['errors']}")
            return None

        remaining = resp.headers.get("x-ratelimit-requests-remaining", "?")
        print(f"  API call OK. Remaining today (API header): {remaining}")
        return data

    except requests.RequestException as e:
        print(f"  Request failed: {e}")
        return None


def load_scores() -> dict:
    if SCORES_FILE.exists():
        return json.loads(SCORES_FILE.read_text(encoding="utf-8"))
    return {}


def save_scores(scores: dict) -> None:
    SCORES_FILE.write_text(
        json.dumps(scores, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def load_matches() -> list[dict]:
    return json.loads(MATCHES_FILE.read_text(encoding="utf-8"))


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching between API and our data."""
    replacements = {
        "USA": "United States",
        "Korea Republic": "South Korea",
        "Turkiye": "Turkey",
        "Türkiye": "Turkey",
        "IR Iran": "Iran",
        "Côte d'Ivoire": "Ivory Coast",
        "Cote D'Ivoire": "Ivory Coast",
        "Congo DR": "DR Congo",
        "Czech Republic": "Czech Republic",
        "Czechia": "Czech Republic",
        "Bosnia Herzegovina": "Bosnia and Herzegovina",
        "Bosnia & Herzegovina": "Bosnia and Herzegovina",
        "Curacao": "Curaçao",
    }
    return replacements.get(name, name)


def find_match_number(matches: list[dict], home: str, away: str, match_date: str) -> int | None:
    """Find our match_number by matching date + team names."""
    home_norm = normalize_team_name(home)
    away_norm = normalize_team_name(away)

    for m in matches:
        if m["date"] != match_date:
            continue
        m_home = m["home"]
        m_away = m["away"]
        if (m_home == home_norm and m_away == away_norm) or \
           (m_home == away_norm and m_away == home_norm):
            return m["match_number"]
    return None


def process_api_fixtures(data: dict, matches: list[dict], scores: dict) -> int:
    """Process API response and update scores dict. Returns count of updates."""
    updated = 0
    for fixture in data.get("response", []):
        status = fixture["fixture"]["status"]["short"]
        goals = fixture.get("goals", {})
        teams = fixture.get("teams", {})

        home_name = teams.get("home", {}).get("name", "")
        away_name = teams.get("away", {}).get("name", "")
        match_date = fixture["fixture"]["date"][:10]

        score_home = goals.get("home")
        score_away = goals.get("away")

        if score_home is None and score_away is None:
            continue

        match_num = find_match_number(matches, home_name, away_name, match_date)
        if match_num is None:
            print(f"  WARN: Could not match {home_name} vs {away_name} on {match_date}")
            continue

        key = str(match_num)
        new_score = {
            "score_home": score_home,
            "score_away": score_away,
            "status": status,
            "api_home": home_name,
            "api_away": away_name,
        }

        if scores.get(key) != new_score:
            scores[key] = new_score
            updated += 1
            status_label = "LIVE" if status not in ("FT", "AET", "PEN") else "FINAL"
            print(f"  [{status_label}] Match #{match_num}: {home_name} {score_home} - {score_away} {away_name} ({status})")

    return updated


def fetch_live(usage: dict) -> None:
    """Fetch live + recently finished matches."""
    print("Fetching live and recent matches...")
    matches = load_matches()
    scores = load_scores()

    params = {
        "league": LEAGUE_ID,
        "season": SEASON,
        "status": "1H-HT-2H-ET-BT-P-FT-AET-PEN",
    }
    data = api_call("fixtures", params, usage)
    if not data:
        return

    updated = process_api_fixtures(data, matches, scores)
    save_scores(scores)
    print(f"  Updated {updated} scores. Total in file: {len(scores)}")


def fetch_final(usage: dict) -> None:
    """Final consolidation — fetch all finished matches."""
    print("Final consolidation — fetching all finished matches...")
    matches = load_matches()
    scores = load_scores()

    params = {
        "league": LEAGUE_ID,
        "season": SEASON,
        "status": "FT-AET-PEN",
    }
    data = api_call("fixtures", params, usage)
    if not data:
        return

    updated = process_api_fixtures(data, matches, scores)
    save_scores(scores)
    print(f"  Updated {updated} scores. Total in file: {len(scores)}")


def show_status(usage: dict) -> None:
    """Show current API usage status."""
    print(f"Date: {usage['date']}")
    print(f"Requests used: {usage['count']}/{DAILY_LIMIT}")
    print(f"Remaining: {DAILY_LIMIT - usage['count']}")
    if usage["calls"]:
        last = usage["calls"][-1]
        print(f"Last call: {last['time']}")

    scores = load_scores()
    finished = sum(1 for s in scores.values() if s.get("status") in ("FT", "AET", "PEN"))
    live = sum(1 for s in scores.values() if s.get("status") not in ("FT", "AET", "PEN", None))
    print(f"\nScores: {len(scores)} total ({finished} finished, {live} live)")


def main():
    parser = argparse.ArgumentParser(description="Update scores from API-Football")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Fetch live + recently finished")
    group.add_argument("--final", action="store_true", help="Final consolidation (all finished)")
    group.add_argument("--manual", nargs=3, metavar=("MATCH", "HOME", "AWAY"),
                       help="Manually set score: match_number home_score away_score")
    group.add_argument("--status", action="store_true", help="Show API usage status")
    args = parser.parse_args()

    usage = load_usage()

    if args.status:
        show_status(usage)
    elif args.manual:
        scores = load_scores()
        match_num, home_score, away_score = args.manual
        scores[match_num] = {
            "score_home": int(home_score),
            "score_away": int(away_score),
            "status": "FT"
        }
        save_scores(scores)
        print(f"Match {match_num}: {home_score} x {away_score} (manually set)")
    elif args.live:
        fetch_live(usage)
    elif args.final:
        fetch_final(usage)


if __name__ == "__main__":
    main()
