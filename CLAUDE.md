# FIFA World Cup 2026 Calendar — Project Context

## Mandatory: Keep documentation in sync

When modifying this project, you MUST update the relevant documentation files in the same commit:

| File | What to update | When |
|---|---|---|
| `CLAUDE.md` | Architecture, file purposes, constraints, format rules, data sources, tech stack | Any structural change (new scripts, new fields, changed logic, new dependencies, new workflows) |
| `OPERATIONS.md` | Procedures, commands, rollback plans, automation details | Any change to operational flow (new scripts, changed CLI args, new workflows, changed API) |
| `README.md` | User-facing instructions, subscription steps, development commands | Any change visible to end users or contributors |
| `docs/index.html` | Installation instructions, format preview, platform steps | Any change to subscription flow, event format, or supported platforms |

Outdated documentation leads to broken code and confused users. If in doubt, update all four.

## What this project does

Generates and serves an .ics calendar file with all 104 FIFA World Cup 2026 matches. Users subscribe via URL on iPhone, Android, or Outlook and receive auto-updated events with live scores, team names in PT-BR, emoji flags, and broadcasting info.

**Live URL (primary):** https://copa2026.trakas.com.br/fifa-worldcup-2026.ics
**Live URL (fallback):** https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics

The primary URL is proxied via Cloudflare Worker (analytics). The fallback serves directly from GitHub Pages. Both serve the same .ics file.

## Architecture

```
matches.json           → Static: schedule, stadiums, TV, streaming (source: Wikipedia)
scores.json            → Dynamic: match results only (source: ESPN + OpenLigaDB)
score_sources/         → Per-source API logic, normalized to ScoreRecord
generate_calendar.py   → Merges matches + scores → sanitize_event() → docs/fifa-worldcup-2026.ics
security/validator.py  → Post-generation scan (CI gate)
```

Separation prevents score updates from corrupting schedule data and vice-versa.
Sanitizer filters every event before .ics generation. Validator scans the output before publishing.

### Score sources (`score_sources/` package)

`update_scores.py` is orchestration + CLI only. Each source talks to its own API
and returns a normalized `ScoreRecord` (canonical team names + UTC kickoff instant),
so the pipeline is source-agnostic.

| Module | Role |
|---|---|
| `score_sources/__init__.py` | `ScoreRecord` dataclass (the common shape) |
| `score_sources/espn.py` | **Primary** live source (real-time). Fetches today + yesterday UTC. `ESPN_NAME_TO_CANONICAL` normalizes 4 divergent names (Czechia, etc.) |
| `score_sources/openligadb.py` | **Fallback** + final-result consolidation. Holds `TEAM_SHORT_TO_NAME` |
| `score_sources/matching.py` | Resolves a `ScoreRecord` to its `match_number` by team pair + UTC instant |

`--live` tries ESPN first and falls back to OpenLigaDB if ESPN returns nothing.
`--final` uses OpenLigaDB (reliable for finished results).

**UTC-vs-local matching:** matches.json stores LOCAL stadium date/time; APIs report UTC.
36 of 104 matches fall on a different UTC day than their local date (evening kickoffs in
the Americas). `matching.py` converts each match to its true UTC instant and matches on
that, fixing a latent bug where the old date-string comparison missed all 36.

## Key files

| File | Purpose |
|---|---|
| `matches.json` | 104 matches with date, time, timezone, stadium, city, tv, streaming. No scores here. |
| `scores.json` | Only scores keyed by match_number. Format: `{"7": {"score_home": 2, "score_away": 0, "status": "FT"}}` |
| `flags.py` | FLAGS (emoji), NAMES_PT_BR (translations), TIMEZONE_ABBR. All team lookups go through here. |
| `generate_calendar.py` | Merges matches + scores → builds .ics with icalendar library. Event format defined here. |
| `fetch_matches.py` | Scrapes Wikipedia (lxml parser, `div.footballbox` class) to populate matches.json. |
| `update_scores.py` | Orchestration + CLI: pulls `ScoreRecord`s from `score_sources/`, matches them, writes scores.json. No API logic. |
| `score_sources/` | Per-source API modules (espn, openligadb) + shared matcher. See "Score sources" above. |
| `update_knockout.py` | Resolves placeholder teams ("Winner Group C" → "Brazil") via OpenLigaDB + Wikipedia fallback. Matches fixtures by UTC kickoff instant (OpenLigaDB) or local date+time (Wikipedia); auto-corrects a wrong real team when the official bracket disagrees. |
| `security/sanitizer.py` | Input sanitization: URL allowlist, CRLF removal, forbidden properties, field limits. |
| `security/validator.py` | Post-generation .ics scanner. Runs standalone or in CI. |
| `security/allowed_domains.json` | Allowlisted streaming/TV domains. URLs outside this list are rejected. |
| `docs/index.html` | Landing page (PT-BR) with subscription instructions per platform. |
| `docs/fifa-worldcup-2026.ics` | Generated output served by GitHub Pages. |
| `OPERATIONS.md` | Full operational procedures, rollback plans, automation details. |

## Event format in .ics

```
Title:    🇧🇷 BRASIL vs Marrocos 🇲🇦 — Grupo C       (no score)
Title:    🇧🇷 BRASIL 2 x 0 Marrocos 🇲🇦 — Grupo C   (with score)
Location: MetLife Stadium, East Rutherford, EUA
Notes:    FIFA World Cup 2026 — Grupo C
          Jogo #7
          🕐 18:00 (ET)
          📺 CazéTV
          🔗 https://www.youtube.com/@CazeTV
```

Rules:
- Team names always in PT-BR (via `flags.get_name_pt()`)
- BRASIL is always uppercase (target audience is Brazilian)
- Score appears in title when `score_home` is not None (live or finished)
- "vs" when no score, "X x Y" with score
- Location field = stadium, city (native calendar location field)
- Time in notes = local timezone of the stadium (the .ics event itself uses TZID for auto-conversion)

## Data sources

| Source | What | Auth | Rate limit |
|---|---|---|---|
| Wikipedia (group pages + knockout page) | Schedule, teams, dates, stadiums | None | None |
| ESPN (`site.api.espn.com/.../fifa.world/scoreboard`) | **Primary** live scores (real-time) | None | Undocumented API — may change without notice |
| OpenLigaDB (`api.openligadb.de`) | **Fallback** scores + knockout team resolution | None | None |
| CazéTV | Broadcasting (hardcoded, all 104 matches) | — | — |

## Automation (GitHub Actions)

| Workflow | When | What |
|---|---|---|
| `update-scores.yml` | Every 20min, all day, Jun–Jul (in-job date check limits to Jun 11 – Jul 19) | Fetches scores → regenerates .ics → auto-commit |
| `update-knockout.yml` | Daily 06:00 UTC, Jun 18 – Jul 19 | Resolves knockout placeholders → auto-commit |
| `tests.yml` | Every push/PR | Unit tests + E2E consistency |

Scheduled triggers skip execution outside tournament window via date check.
Manual triggers (`workflow_dispatch`) bypass the date check for testing.
Requires repo Settings → Actions → Workflow permissions → "Read and write permissions" for auto-commit.

## Testing

```bash
python -m pytest tests/ -v         # All 175 tests
python -m pytest tests/ --ignore=tests/test_e2e_consistency.py  # Unit + security (no network)
python -m pytest tests/test_e2e_consistency.py -v               # E2E vs Wikipedia
python -m pytest tests/test_security.py -v                      # Security tests only
E2E_SAMPLE_SIZE=15 python -m pytest tests/test_e2e_consistency.py  # More samples
python -m security.validator                                    # Standalone .ics scan
```

Tests enforce:
- matches.json integrity (104 matches, 6/group, valid dates, no duplicates)
- Title format with/without scores, BRASIL uppercase
- Score merge doesn't mutate original data
- Team name normalization covers all API variants
- Knockout matching uses UTC kickoff instant (prevents cross-assignment across timezones)
- Knockout auto-corrects a wrong real team when the official bracket disagrees
- E2E: random matches validated against live Wikipedia
- Security: URL allowlist, CRLF injection, forbidden properties, field limits
- .ics output scanned for VALARM, ATTACH, ATTENDEE, non-HTTPS URLs

## Important constraints

- `matches.json` NEVER contains score fields — those live in `scores.json`
- `update_knockout.py` never replaces a real team with a placeholder, but DOES auto-correct a wrong real team when the official source (OpenLigaDB/Wikipedia) disagrees — this is what un-freezes an earlier cross-assignment
- Knockout matching uses the UTC kickoff instant (OpenLigaDB) to differentiate multiple matches on the same day, robust to timezone/DST
- Pre-commit hook runs all 175 tests before allowing commits
- Calendar refresh interval is 6 hours (PT6H in .ics)
- All URLs in the .ics must be HTTPS and from `security/allowed_domains.json`
- Branch protection requires PR + passing status checks for merge to main
- generate_calendar.py passes every event through `security.sanitizer.sanitize_event()` before adding to .ics

## Wikipedia parsing notes

- Parser: `lxml` (required — `html.parser` fails to find `footballbox` divs)
- Match structure: `div.footballbox` containing `.fleft` (date/time), `.fevent` (teams/score), `.fright` (venue)
- Date is in `span.bday` inside `.fdate`
- Time is in `.ftime` (12h format like "6:00 p.m." — converted via `parse_time_12h()`)
- Knockout page has all matches inside a bracket TABLE, not separated by H2 headings — stage classified by date ranges

## Rollback procedures

**Corrupted matches.json:** `python fetch_matches.py` (re-scrapes Wikipedia, restores placeholders)
**Corrupted scores.json:** `echo '{}' > scores.json` (scores rebuild on next `update_scores.py --live` call)
**Bad knockout update:** `git checkout HEAD~1 -- matches.json`

## Security

4-layer security model protects subscribers from malicious content:

```
security/
├── sanitizer.py         ← Input sanitization (called by generate_calendar.py)
├── allowed_domains.json ← URL allowlist (youtube, globo, cazetv, etc.)
└── validator.py         ← Post-generation .ics scan (runs in CI)
```

**Protections:**
- URL allowlist: only trusted streaming domains (rejects anything else)
- CRLF injection removal from all text fields
- Forbidden ICS properties blocked: VALARM, ATTACH, ATTENDEE, TZURL, ORGANIZER
- Forbidden schemes blocked: javascript:, data:, file://, ftp://, vbscript:
- Field length limits: SUMMARY 200, DESCRIPTION 500, LOCATION 200
- matches.json scanned for hidden URLs and script tags
- Branch protection: PRs required, status checks must pass, force push blocked

**Adding a new streaming domain:**
Add to `security/allowed_domains.json` — must be exact domain (no wildcards).

## Tech stack

- Python 3.12+
- icalendar, requests, beautifulsoup4, lxml, pytest
- GitHub Pages (serves /docs)
- GitHub Actions (automation)
