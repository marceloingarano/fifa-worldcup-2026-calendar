#!/usr/bin/env python3
"""
Update scores.json from an external API.

This script fetches live/final scores and writes them to scores.json
without touching matches.json. The generate_calendar.py script merges
both files when generating the .ics.

Usage:
    python update_scores.py              # Fetch and update all scores
    python update_scores.py --match 7    # Update a specific match only
    python update_scores.py --manual 7 2 0  # Manually set: match 7, home 2, away 0

Configure API_URL and adapt fetch_scores_from_api() to your API format.
"""

import argparse
import json
from pathlib import Path

import requests

SCORES_FILE = Path(__file__).parent / "scores.json"

# --- API Configuration ---
# Replace with your actual API endpoint
API_URL = ""
API_HEADERS = {}


def load_scores() -> dict:
    if SCORES_FILE.exists():
        return json.loads(SCORES_FILE.read_text(encoding="utf-8"))
    return {}


def save_scores(scores: dict) -> None:
    SCORES_FILE.write_text(
        json.dumps(scores, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def fetch_scores_from_api(match_number: int | None = None) -> dict:
    """
    Fetch scores from external API.

    Expected return format:
    {
        "7": {"score_home": 2, "score_away": 0, "status": "finished"},
        "8": {"score_home": 1, "score_away": 1, "status": "live"},
        ...
    }

    Status values: "scheduled", "live", "finished"
    """
    if not API_URL:
        print("API_URL not configured. Use --manual to set scores or configure the API.")
        return {}

    try:
        params = {}
        if match_number:
            params["match"] = match_number

        resp = requests.get(API_URL, headers=API_HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # --- Adapt this section to your API response format ---
        # Example: if API returns a list of matches
        # scores = {}
        # for item in data["matches"]:
        #     key = str(item["match_number"])
        #     scores[key] = {
        #         "score_home": item["home_score"],
        #         "score_away": item["away_score"],
        #         "status": item["status"],
        #     }
        # return scores

        return data

    except requests.RequestException as e:
        print(f"API error: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Update scores.json")
    parser.add_argument("--match", type=int, help="Fetch score for specific match number")
    parser.add_argument("--manual", nargs=3, metavar=("MATCH", "HOME", "AWAY"),
                        help="Manually set score: match_number home_score away_score")
    args = parser.parse_args()

    scores = load_scores()

    if args.manual:
        match_num, home_score, away_score = args.manual
        scores[match_num] = {
            "score_home": int(home_score),
            "score_away": int(away_score),
            "status": "finished"
        }
        save_scores(scores)
        print(f"Match {match_num}: {home_score} x {away_score} (manually set)")
    else:
        new_scores = fetch_scores_from_api(args.match)
        if new_scores:
            scores.update(new_scores)
            save_scores(scores)
            print(f"Updated {len(new_scores)} scores")
        else:
            print("No scores to update")

    print(f"Total scores in file: {len(scores)}")


if __name__ == "__main__":
    main()
