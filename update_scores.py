#!/usr/bin/env python3
"""Update scores.json from live score sources.

Sources (see score_sources/):
    ESPN        — primary, real-time live scores
    OpenLigaDB  — fallback + final-result consolidation

This module is orchestration + CLI only. All API logic lives in the per-source
modules; matching lives in score_sources.matching. Every source emits the same
normalized ScoreRecord, so the logic here is source-agnostic.

Modes:
    python update_scores.py --live          # ESPN, fallback to OpenLigaDB
    python update_scores.py --final         # OpenLigaDB final consolidation
    python update_scores.py --manual 7 2 0  # Manually set: match 7, home 2, away 0
    python update_scores.py --status        # Show current scores summary
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from score_sources import ScoreRecord, espn, openligadb
from score_sources.matching import resolve_match_number

SCORES_FILE = Path(__file__).parent / "scores.json"
MATCHES_FILE = Path(__file__).parent / "matches.json"


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


def apply_records(records: list[ScoreRecord], matches: list[dict], scores: dict) -> int:
    """Merge ScoreRecords into the scores dict. Returns count of changed entries.

    Idempotent: only writes when the score or status actually changed.
    """
    updated = 0
    for record in records:
        match_num = resolve_match_number(matches, record.home, record.away, record.utc)
        if match_num is None:
            print(f"  WARN: could not match {record.home} vs {record.away} @ {record.utc.isoformat()}")
            continue

        key = str(match_num)
        new_score = {
            "score_home": record.score_home,
            "score_away": record.score_away,
            "status": record.status,
        }

        existing = scores.get(key, {})
        if existing.get("score_home") != record.score_home or \
           existing.get("score_away") != record.score_away or \
           existing.get("status") != record.status:
            scores[key] = new_score
            updated += 1
            label = "FINAL" if record.status == "FT" else "LIVE"
            print(f"  [{label}] #{match_num}: {record.home} {record.score_home} - {record.score_away} {record.away}")

    return updated


def cmd_live():
    """Fetch live + finished scores: ESPN first, OpenLigaDB as fallback."""
    matches = load_matches()
    scores = load_scores()

    today = datetime.now(timezone.utc).date()
    print("Fetching live scores from ESPN...")
    records = espn.fetch(today)
    source = "ESPN"

    if not records:
        print("ESPN returned nothing — falling back to OpenLigaDB...")
        records = openligadb.fetch()
        source = "OpenLigaDB"

    updated = apply_records(records, matches, scores)
    save_scores(scores)
    print(f"\nSource: {source}. Updated {updated} scores. Total in file: {len(scores)}")


def cmd_final():
    """Final consolidation — OpenLigaDB finished results only."""
    print("Final consolidation — fetching from OpenLigaDB...")
    matches = load_matches()
    scores = load_scores()

    records = [r for r in openligadb.fetch() if r.status == "FT"]
    updated = apply_records(records, matches, scores)

    save_scores(scores)
    print(f"\nUpdated {updated} scores. Total in file: {len(scores)}")


def cmd_status():
    """Show current scores summary."""
    scores = load_scores()
    finished = sum(1 for s in scores.values() if s.get("status") == "FT")
    live = sum(1 for s in scores.values() if s.get("status") == "LIVE")
    print(f"Scores: {len(scores)} total ({finished} finished, {live} live)")
    print("Sources: ESPN (primary, live) + OpenLigaDB (fallback, final)")


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
    parser = argparse.ArgumentParser(description="Update scores from live sources")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--live", action="store_true", help="Fetch live + finished (ESPN, fallback OpenLigaDB)")
    group.add_argument("--final", action="store_true", help="Final consolidation (OpenLigaDB, finished only)")
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
