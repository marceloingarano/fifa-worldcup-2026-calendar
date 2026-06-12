"""OpenLigaDB score source (free, no auth, no rate limit).

API: https://api.openligadb.de  — League: wm26 (FIFA World Cup 2026)

Reliable for FINAL results (end-of-day consolidation) but slow/incomplete for
live scores — which is why ESPN is the primary live source and this is the
fallback. See OPERATIONS.md.

`fetch()` returns a list of normalized `ScoreRecord` (canonical team names,
UTC kickoff instant). Raw-payload helpers are kept module-level and unit-tested
directly.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import ScoreRecord

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

# OpenLigaDB short codes -> canonical team names (matches.json keys).
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


def resolve_team_name(api_match: dict, team_key: str) -> str:
    """Resolve team name from API short code to our canonical name."""
    team = api_match[team_key]
    short = team.get("shortName", "")
    return TEAM_SHORT_TO_NAME.get(short, team.get("teamName", ""))


def extract_final_score(api_match: dict) -> tuple[int | None, int | None]:
    """Extract final score from matchResults. Returns (home_goals, away_goals).

    OpenLigaDB returns multiple results per match. The final score is the one
    named "Endergebnis" (resultTypeID == 2). resultOrderID == 1 is the FIRST
    chronological result, which becomes "Halbzeit" (half-time) once the match
    passes the first half — NOT the final score.
    """
    results = api_match.get("matchResults", [])

    # Preferred: the official final result.
    for result in results:
        if result.get("resultName") == "Endergebnis" or result.get("resultTypeID") == 2:
            return result["pointsTeam1"], result["pointsTeam2"]

    # Fallback: highest resultOrderID = most recent live result (e.g. half-time
    # while a match is still LIVE and no final result exists yet).
    if results:
        latest = max(results, key=lambda r: r.get("resultOrderID", 0))
        return latest["pointsTeam1"], latest["pointsTeam2"]
    return None, None


def determine_status(api_match: dict) -> str:
    """Determine match status from API data: FT / LIVE / NS."""
    if api_match.get("matchIsFinished"):
        return "FT"
    if api_match.get("matchResults"):
        return "LIVE"
    return "NS"


def _parse_utc(api_match: dict) -> datetime | None:
    """Parse matchDateTimeUTC into a tz-aware UTC datetime."""
    raw = api_match.get("matchDateTimeUTC", "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(ZoneInfo("UTC"))
    except Exception:
        return None


def to_record(api_match: dict) -> ScoreRecord | None:
    """Convert one OpenLigaDB match payload into a ScoreRecord.

    Returns None for not-started matches (no usable score yet) or unparseable
    kickoff times.
    """
    status = determine_status(api_match)
    if status == "NS":
        return None

    score_home, score_away = extract_final_score(api_match)
    if score_home is None:
        return None

    kickoff = _parse_utc(api_match)
    if kickoff is None:
        return None

    return ScoreRecord(
        home=resolve_team_name(api_match, "team1"),
        away=resolve_team_name(api_match, "team2"),
        utc=kickoff,
        score_home=score_home,
        score_away=score_away,
        status=status,
    )


def _fetch_all_matchdays() -> list[dict]:
    """Fetch raw match payloads for all 8 matchdays from OpenLigaDB."""
    all_data = []
    for matchday in range(1, 9):
        url = f"{API_BASE_URL}/getmatchdata/{LEAGUE_SHORTCUT}/{SEASON}/{matchday}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            all_data.extend(data)
            print(f"  [OpenLigaDB] Matchday {matchday} ({MATCHDAYS.get(matchday, '?')}): {len(data)} matches")
        except requests.RequestException as e:
            print(f"  [OpenLigaDB] Matchday {matchday}: ERROR - {e}")
    return all_data


def fetch() -> list[ScoreRecord]:
    """Fetch all matches with usable scores from OpenLigaDB as ScoreRecords."""
    records = []
    for api_match in _fetch_all_matchdays():
        record = to_record(api_match)
        if record is not None:
            records.append(record)
    return records
