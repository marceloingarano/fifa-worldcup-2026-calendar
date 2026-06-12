"""ESPN score source (free, no auth) — primary live-score provider.

Endpoint (undocumented public API that powers ESPN's site):
    https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard

Chosen as the primary live source because it reports in-progress matches in
real time (status + minute), where OpenLigaDB lags badly. Being undocumented,
it can change without notice — hence OpenLigaDB stays as fallback.

The scoreboard returns only the current matchday by default; a specific day is
fetched via ?dates=YYYYMMDD. To catch evening matches in the Americas that roll
into the next UTC day while still live, we fetch TODAY and YESTERDAY (UTC).

`fetch(today)` takes the current UTC date as an argument (injectable for tests)
and returns normalized `ScoreRecord`s with canonical team names.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from . import ScoreRecord

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# ESPN displayName -> canonical name (matches.json key). Only divergences need
# an entry; everything else matches matches.json verbatim (audited against all
# 48 teams). Update if ESPN renames a team.
ESPN_NAME_TO_CANONICAL = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
}

# ESPN status.type.state -> our status vocabulary.
_STATE_TO_STATUS = {
    "post": "FT",
    "in": "LIVE",
    "pre": "NS",
}


def resolve_espn_name(competitor: dict) -> str:
    """Resolve an ESPN competitor's team to a canonical name."""
    name = competitor.get("team", {}).get("displayName", "")
    return ESPN_NAME_TO_CANONICAL.get(name, name)


def determine_espn_status(competition: dict) -> str:
    """Map ESPN status.type.state to FT / LIVE / NS (defaults to NS)."""
    state = competition.get("status", {}).get("type", {}).get("state", "")
    return _STATE_TO_STATUS.get(state, "NS")


def _parse_utc(event: dict) -> datetime | None:
    """Parse the event's ISO date into a tz-aware UTC datetime."""
    raw = event.get("date", "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(ZoneInfo("UTC"))
    except Exception:
        return None


def _score(competitor: dict) -> int | None:
    """Parse a competitor's score (ESPN returns it as a string)."""
    raw = competitor.get("score")
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def to_record(event: dict) -> ScoreRecord | None:
    """Convert one ESPN event into a ScoreRecord.

    Returns None for not-started matches (no usable score yet), unparseable
    kickoff times, or malformed competitor lists.
    """
    competition = (event.get("competitions") or [{}])[0]
    status = determine_espn_status(competition)
    if status == "NS":
        return None

    competitors = competition.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if home is None or away is None:
        return None

    score_home = _score(home)
    score_away = _score(away)
    if score_home is None or score_away is None:
        return None

    kickoff = _parse_utc(event)
    if kickoff is None:
        return None

    return ScoreRecord(
        home=resolve_espn_name(home),
        away=resolve_espn_name(away),
        utc=kickoff,
        score_home=score_home,
        score_away=score_away,
        status=status,
    )


def _fetch_day(day: date) -> list[dict]:
    """Fetch raw events for a single UTC day from the ESPN scoreboard."""
    url = f"{ESPN_BASE_URL}?dates={day.strftime('%Y%m%d')}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        events = resp.json().get("events", [])
        print(f"  [ESPN] {day.isoformat()}: {len(events)} events")
        return events
    except requests.RequestException as e:
        print(f"  [ESPN] {day.isoformat()}: ERROR - {e}")
        return []


def fetch(today: date) -> list[ScoreRecord]:
    """Fetch ScoreRecords for today and yesterday (UTC).

    `today` is the current UTC date, passed in by the caller so this stays
    deterministic and testable. Yesterday is included so evening matches in the
    Americas (which roll into the next UTC day) are still captured while live.
    """
    records = []
    for day in (today, today - timedelta(days=1)):
        for event in _fetch_day(day):
            record = to_record(event)
            if record is not None:
                records.append(record)
    return records
