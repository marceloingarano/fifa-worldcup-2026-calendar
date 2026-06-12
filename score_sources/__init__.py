"""Score sources for the FIFA World Cup 2026 calendar.

Each source (ESPN, OpenLigaDB) knows how to talk to its own API and returns a
list of `ScoreRecord` — a normalized, source-agnostic shape. The rest of the
pipeline (matching, scores.json I/O) works only with `ScoreRecord` and never
sees the raw API payloads.

Team names in a `ScoreRecord` are always canonical (the keys used in
matches.json / flags.NAMES_PT_BR), so matching is uniform across sources.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScoreRecord:
    """A single match result normalized from any score source.

    Attributes:
        home: Canonical home team name (matches.json key).
        away: Canonical away team name (matches.json key).
        utc: Kickoff instant in UTC (tz-aware datetime).
        score_home: Home goals, or None if no score is available yet.
        score_away: Away goals, or None if no score is available yet.
        status: One of "FT" (finished), "LIVE" (in progress), "NS" (not started).
    """

    home: str
    away: str
    utc: datetime
    score_home: int | None
    score_away: int | None
    status: str


__all__ = ["ScoreRecord"]
