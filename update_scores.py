#!/usr/bin/env python3
"""
Update scores.json from OpenLigaDB (free, no auth, no rate limit).

API: https://api.openligadb.de
League: wm26 (FIFA World Cup 2026)

Modes:
    python update_scores.py --live         # Fetch all matches (live + finished)
    python update_scores.py --final        # Fetch only finished matches
    python update_scores.py --manual 7 2 0 # Manually set: match 7, home 2, away 0
    python update_scores.py --status       # Show current scores summary
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

SCORES_FILE = Path(__file__).parent / "scores.json"
MATCHES_FILE = Path(__file__).parent / "matches.json"

API_BASE_URL = "https://api.openligadb.de"
LEAGUE_SHORTCUT = "wm26"
SEASON = 2026

MATCHDAYS = {
    1: "Gruppenphase 1",
    2: "Gruppenphase 2",
    3: "Gruppenphase 3",
    4: "Sechzehntelfinale",  # Round of 32
    5: "Achtelfinale",       # Round of 16
    6: "Viertelfinale",      # Quarter-finals
    7: "Halbfinale",         # Semi-finals
    8: "Finale",             # Final + Third place
}

# Mapping from OpenLigaDB short codes to our team names in matches.json
TEAM_SHORT_TO_NAME = {
    "MEX": "Mexico",
    "RSA": "South Africa",
    "KOR": "South Korea",
    "CZE": "Czech Republic",
    "CAN": "Canada",
    "BIH": "Bosnia and Herzegovina",
    "QAT": "Qatar",
    "CHE": "Switzerland",
    "BRA": "Brazil",
    "MAR": "Morocco",
    "HTI": "Haiti",
    "SCT": "Scotland",
    "USA": "United States",
    "PAR": "Paraguay",
    "AUS": "Australia",
    "TUR": "Turkey",
    "DEU": "Germany",
    "CUW": "Curaçao",
    "CIV": "Ivory Coast",
    "ECU": "Ecuador",
    "NLD": "Netherlands",
    "JPN": "Japan",
    "SWE": "Sweden",
    "TUN": "Tunisia",
    "BEL": "Belgium",
    "EGY": "Egypt",
    "IRN": "Iran",
    "NZL": "New Zealand",
    "ESP": "Spain",
    "CPV": "Cape Verde",
    "SAU": "Saudi Arabia",
    "URY": "Uruguay",
    "FRA": "France",
    "SEN": "Senegal",
    "IRQ": "Iraq",
    "NOR": "Norway",
    "ARG": "Argentina",
    "DZA": "Algeria",
    "AUT": "Austria",
    "JOR": "Jordan",
    "PRT": "Portugal",
    "COD": "DR Congo",
    "UZB": "Uzbekistan",
    "COL": "Colombia",
    "ENG": "England",
    "HRV": "Croatia",
    "GHA": "Ghana",
    "PAN": "Panama",
}


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


def resolve_team_name(api_match: dict, team_key: str) -> str:
    """Resolve team name from API short code to our matches.json name."""
    team = api_match[team_key]
    short = team.get("shortName", "")
    return TEAM_SHORT_TO_NAME.get(short, team.get("teamName", ""))


def find_match_number(matches: list[dict], home: str, away: str, match_date: str) -> int | None:
    """Find our match_number by date + team names."""
    for m in matches:
        if m["date"] != match_date:
            continue
        if (m["home"] == home and m["away"] == away) or \
           (m["home"] == away and m["away"] == home):
            return m["match_number"]
    return None


def extract_final_score(api_match: dict) -> tuple[int | None, int | None]:
    """Extract final score from matchResults. Returns (home_goals, away_goals)."""
    for result in api_match.get("matchResults", []):
        if result.get("resultOrderID") == 1:  # Endergebnis = final result
            return result["pointsTeam1"], result["pointsTeam2"]
    # Fallback: check if there's any result
    if api_match.get("matchResults"):
        last = api_match["matchResults"][0]
        return last["pointsTeam1"], last["pointsTeam2"]
    return None, None


def determine_status(api_match: dict) -> str:
    """Determine match status from API data."""
    if api_match.get("matchIsFinished"):
        return "FT"
    if api_match.get("matchResults"):
        return "LIVE"
    return "NS"


def fetch_all_matches() -> list[dict]:
    """Fetch all WC 2026 matches from OpenLigaDB."""
    all_data = []
    for matchday in range(1, 9):
        url = f"{API_BASE_URL}/getmatchdata/{LEAGUE_SHORTCUT}/{SEASON}/{matchday}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_data.extend(data)
            print(f"  Matchday {matchday} ({MATCHDAYS.get(matchday, '?')}): {len(data)} matches")
        except requests.RequestException as e:
            print(f"  Matchday {matchday}: ERROR - {e}")
    return all_data


def process_api_data(api_data: list[dict], matches: list[dict], scores: dict,
                     only_finished: bool = False) -> int:
    """Process API response and update scores dict. Returns count of updates."""
    updated = 0

    for api_match in api_data:
        status = determine_status(api_match)

        if only_finished and status != "FT":
            continue

        if status == "NS":
            continue

        score_home, score_away = extract_final_score(api_match)
        if score_home is None:
            continue

        home_name = resolve_team_name(api_match, "team1")
        away_name = resolve_team_name(api_match, "team2")
        match_date = api_match.get("matchDateTimeUTC", "")[:10]

        match_num = find_match_number(matches, home_name, away_name, match_date)
        if match_num is None:
            print(f"  WARN: Could not match {home_name} vs {away_name} on {match_date}")
            continue

        key = str(match_num)
        new_score = {
            "score_home": score_home,
            "score_away": score_away,
            "status": status,
        }

        existing = scores.get(key, {})
        if existing.get("score_home") != score_home or \
           existing.get("score_away") != score_away or \
           existing.get("status") != status:
            scores[key] = new_score
            updated += 1
            label = "FINAL" if status == "FT" else "LIVE"
            print(f"  [{label}] #{match_num}: {home_name} {score_home} - {score_away} {away_name}")

    return updated


def cmd_live():
    """Fetch all matches with scores (live + finished)."""
    print("Fetching all matches from OpenLigaDB...")
    matches = load_matches()
    scores = load_scores()

    api_data = fetch_all_matches()
    updated = process_api_data(api_data, matches, scores, only_finished=False)

    save_scores(scores)
    print(f"\nUpdated {updated} scores. Total in file: {len(scores)}")


def cmd_final():
    """Fetch only finished matches (end-of-day consolidation)."""
    print("Final consolidation — fetching finished matches...")
    matches = load_matches()
    scores = load_scores()

    api_data = fetch_all_matches()
    updated = process_api_data(api_data, matches, scores, only_finished=True)

    save_scores(scores)
    print(f"\nUpdated {updated} scores. Total in file: {len(scores)}")


def cmd_status():
    """Show current scores summary."""
    scores = load_scores()
    finished = sum(1 for s in scores.values() if s.get("status") == "FT")
    live = sum(1 for s in scores.values() if s.get("status") == "LIVE")
    print(f"Scores: {len(scores)} total ({finished} finished, {live} live)")
    print(f"API: OpenLigaDB (free, no auth, no rate limit)")
    print(f"League: {LEAGUE_SHORTCUT} / Season: {SEASON}")


def cmd_manual(match_num: str, home_score: str, away_score: str):
    """Manually set a score."""
    scores = load_scores()
    scores[match_num] = {
        "score_home": int(home_score),
        "score_away": int(away_score),
        "status": "FT"
    }
    save_scores(scores)
    print(f"Match {match_num}: {home_score} x {away_score} (manually set)")


def main():
    parser = argparse.ArgumentParser(description="Update scores from OpenLigaDB")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Fetch live + finished scores")
    group.add_argument("--final", action="store_true", help="Final consolidation (finished only)")
    group.add_argument("--manual", nargs=3, metavar=("MATCH", "HOME", "AWAY"),
                       help="Manually set score: match_number home_score away_score")
    group.add_argument("--status", action="store_true", help="Show scores summary")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.manual:
        cmd_manual(*args.manual)
    elif args.live:
        cmd_live()
    elif args.final:
        cmd_final()


if __name__ == "__main__":
    main()
