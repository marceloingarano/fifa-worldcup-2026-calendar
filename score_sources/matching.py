"""Match a normalized ScoreRecord back to its match_number in matches.json.

matches.json stores LOCAL stadium date + time + timezone. APIs report UTC.
36 of the 104 matches kick off in the evening in the Americas and therefore
fall on a DIFFERENT calendar day in UTC than their local date (e.g. match #2,
Korea vs Czech: local 2026-06-11 20:00 Mexico City = 2026-06-12 02:00 UTC).

The old date-string comparison (matchDateTimeUTC[:10] == m["date"]) silently
failed for all 36 of those matches. This matcher instead derives each match's
true UTC kickoff instant and compares instants, so the day boundary never
matters.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# A record kicks off at the same instant as its matches.json entry; allow a
# generous window to absorb schedule/API drift while staying far below the
# gap between two matches of the same pairing (which never repeats same-day).
_MATCH_WINDOW = timedelta(hours=6)


def match_utc_instant(match: dict) -> datetime | None:
    """Convert a matches.json entry's local date+time+timezone to a UTC instant.

    Returns a tz-aware UTC datetime, or None if the fields are missing/invalid.
    """
    date = match.get("date", "")
    time = match.get("time", "")
    tz = match.get("timezone", "")
    if not (date and time and tz):
        return None
    try:
        local = datetime(
            int(date[0:4]), int(date[5:7]), int(date[8:10]),
            int(time[0:2]), int(time[3:5]),
            tzinfo=ZoneInfo(tz),
        )
        return local.astimezone(ZoneInfo("UTC"))
    except Exception:
        return None


def find_match_by_instant(matches: list[dict], kickoff_utc: datetime,
                          predicate=None) -> dict | None:
    """Find the match whose UTC kickoff instant is closest to kickoff_utc.

    Unlike resolve_match_number (which keys on the team pair), this keys ONLY on
    the kickoff instant — used for knockout matches whose teams are still
    placeholders. An optional predicate(match) -> bool filters candidates
    (e.g. "knockout matches only"). Returns the closest match within
    _MATCH_WINDOW, or None.
    """
    best = None
    best_delta = _MATCH_WINDOW
    for m in matches:
        if predicate is not None and not predicate(m):
            continue
        instant = match_utc_instant(m)
        if instant is None:
            continue
        delta = abs(instant - kickoff_utc)
        if delta <= best_delta:
            best_delta = delta
            best = m
    return best


def resolve_match_number(matches: list[dict], home: str, away: str,
                         kickoff_utc: datetime) -> int | None:
    """Find a match_number by canonical team pair + UTC kickoff instant.

    Team order is ignored (home/away may differ between source and matches.json).
    Among matches with the same pairing, the one whose UTC instant is closest to
    kickoff_utc wins, provided it falls within _MATCH_WINDOW.
    """
    best_num = None
    best_delta = _MATCH_WINDOW
    pair = {home, away}
    for m in matches:
        if {m["home"], m["away"]} != pair:
            continue
        instant = match_utc_instant(m)
        if instant is None:
            continue
        delta = abs(instant - kickoff_utc)
        if delta <= best_delta:
            best_delta = delta
            best_num = m["match_number"]
    return best_num
