#!/usr/bin/env python3
"""Generate an .ics calendar file for FIFA World Cup 2026."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from flags import get_flag, get_name_pt, get_tz_abbr

MATCHES_FILE = Path(__file__).parent / "matches.json"
SCORES_FILE = Path(__file__).parent / "scores.json"
OUTPUT_FILE = Path(__file__).parent / "docs" / "fifa-worldcup-2026.ics"
MATCH_DURATION_MINUTES = 120


def build_event_title(match: dict) -> str:
    home = match["home"]
    away = match["away"]
    flag_home = get_flag(home)
    flag_away = get_flag(away)
    name_home = get_name_pt(home)
    name_away = get_name_pt(away)
    stage = match["stage"]

    has_score = match.get("score_home") is not None and match.get("score_away") is not None

    if has_score:
        title = f"{flag_home} {name_home} {match['score_home']} x {match['score_away']} {name_away} {flag_away} — {stage}"
    else:
        title = f"{flag_home} {name_home} vs {name_away} {flag_away} — {stage}"

    return title


def build_event_description(match: dict) -> str:
    tz_abbr = get_tz_abbr(match["timezone"])
    lines = [
        f"FIFA World Cup 2026 — {match['stage']}",
        f"Jogo #{match['match_number']}",
        f"\U0001f550 {match['time']} ({tz_abbr})",
    ]
    if match.get("tv"):
        lines.append(f"\U0001f4fa {match['tv']}")
    if match.get("streaming"):
        lines.append(f"\U0001f517 {match['streaming']}")
    return "\n".join(lines)


def build_event_location(match: dict) -> str:
    if match["stadium"] == "TBD":
        return "A definir"
    return f"{match['stadium']}, {match['city']}"


def create_calendar() -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//FIFA World Cup 2026//github.com//")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Copa do Mundo FIFA 2026")
    cal.add("x-wr-timezone", "America/Sao_Paulo")
    cal.add("refresh-interval;value=duration", "PT6H")
    cal.add("x-published-ttl", "PT6H")
    return cal


def add_match_event(cal: Calendar, match: dict) -> None:
    tz = ZoneInfo(match["timezone"])
    dt_start = datetime.strptime(f"{match['date']} {match['time']}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    dt_end = dt_start + timedelta(minutes=MATCH_DURATION_MINUTES)

    event = Event()
    event.add("summary", build_event_title(match))
    event.add("dtstart", dt_start)
    event.add("dtend", dt_end)
    event.add("location", build_event_location(match))
    event.add("description", build_event_description(match))
    event.add("uid", f"fifawc2026-match{match['match_number']:03d}@github.com")
    event.add("dtstamp", datetime.now(tz=ZoneInfo("UTC")))
    event.add("categories", [match["stage"]])
    event.add("status", "CONFIRMED")

    cal.add_component(event)


def load_scores() -> dict:
    """Load scores from scores.json. Returns dict keyed by match_number (str)."""
    if not SCORES_FILE.exists():
        return {}
    return json.loads(SCORES_FILE.read_text(encoding="utf-8"))


def merge_scores(matches: list[dict], scores: dict) -> list[dict]:
    """Merge score data into match list without modifying matches.json."""
    merged = []
    for match in matches:
        m = dict(match)
        key = str(m["match_number"])
        if key in scores:
            m["score_home"] = scores[key].get("score_home")
            m["score_away"] = scores[key].get("score_away")
        else:
            m["score_home"] = None
            m["score_away"] = None
        merged.append(m)
    return merged


def main():
    matches = json.loads(MATCHES_FILE.read_text(encoding="utf-8"))
    scores = load_scores()
    matches = merge_scores(matches, scores)
    cal = create_calendar()

    for match in sorted(matches, key=lambda m: (m["date"], m["time"])):
        add_match_event(cal, match)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_bytes(cal.to_ical())
    print(f"Generated {OUTPUT_FILE} with {len(matches)} matches ({len(scores)} with scores)")


if __name__ == "__main__":
    main()
