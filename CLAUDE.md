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

**Live URL:** https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics

## Architecture

```
matches.json           → Static: schedule, stadiums, TV, streaming (source: Wikipedia)
scores.json            → Dynamic: match results only (source: OpenLigaDB API)
generate_calendar.py   → Merges both → docs/fifa-worldcup-2026.ics
```

Separation prevents score updates from corrupting schedule data and vice-versa.

## Key files

| File | Purpose |
|---|---|
| `matches.json` | 104 matches with date, time, timezone, stadium, city, tv, streaming. No scores here. |
| `scores.json` | Only scores keyed by match_number. Format: `{"7": {"score_home": 2, "score_away": 0, "status": "FT"}}` |
| `flags.py` | FLAGS (emoji), NAMES_PT_BR (translations), TIMEZONE_ABBR. All team lookups go through here. |
| `generate_calendar.py` | Merges matches + scores → builds .ics with icalendar library. Event format defined here. |
| `fetch_matches.py` | Scrapes Wikipedia (lxml parser, `div.footballbox` class) to populate matches.json. |
| `update_scores.py` | Fetches live/final scores from OpenLigaDB (free, no auth). |
| `update_knockout.py` | Resolves placeholder teams ("Winner Group C" → "Brazil") via OpenLigaDB + Wikipedia fallback. |
| `docs/index.html` | Landing page (PT-BR) with subscription instructions. |
| `docs/fifa-worldcup-2026.ics` | Generated output served by GitHub Pages. |
| `OPERATIONS.md` | Full operational procedures, rollback plans, automation details. |

## Event format in .ics

```
Title:    🇧🇷 Brasil vs Marrocos 🇲🇦 — Grupo C       (no score)
Title:    🇧🇷 Brasil 2 x 0 Marrocos 🇲🇦 — Grupo C   (with score)
Location: MetLife Stadium, East Rutherford, EUA
Notes:    FIFA World Cup 2026 — Grupo C
          Jogo #7
          🕐 18:00 (ET)
          📺 CazéTV
          🔗 https://www.youtube.com/@CasimiroMiguel
```

Rules:
- Team names always in PT-BR (via `flags.get_name_pt()`)
- Score appears in title when `score_home` is not None (live or finished)
- "vs" when no score, "X x Y" with score
- Location field = stadium, city (native calendar location field)
- Time in notes = local timezone of the stadium (the .ics event itself uses TZID for auto-conversion)

## Data sources

| Source | What | Auth | Rate limit |
|---|---|---|---|
| Wikipedia (group pages + knockout page) | Schedule, teams, dates, stadiums | None | None |
| OpenLigaDB (`api.openligadb.de`) | Live scores + knockout team resolution | None | None |
| CazéTV | Broadcasting (hardcoded, all 104 matches) | — | — |

## Automation (GitHub Actions)

| Workflow | When | What |
|---|---|---|
| `update-scores.yml` | Every 10min, Jun 11 – Jul 19, match hours | Fetches scores → regenerates .ics → auto-commit |
| `update-knockout.yml` | Daily 06:00 UTC, Jun 27 – Jul 19 | Resolves knockout placeholders → auto-commit |
| `tests.yml` | Every push/PR | Unit tests + E2E consistency |

Both skip execution outside tournament window via date check.

## Testing

```bash
python -m pytest tests/ -v         # All 115 tests
python -m pytest tests/ --ignore=tests/test_e2e_consistency.py  # Unit only (no network)
python -m pytest tests/test_e2e_consistency.py -v               # E2E vs Wikipedia
E2E_SAMPLE_SIZE=15 python -m pytest tests/test_e2e_consistency.py  # More samples
```

Tests enforce:
- matches.json integrity (104 matches, 6/group, valid dates, no duplicates)
- Title format with/without scores
- Score merge doesn't mutate original data
- Team name normalization covers all API variants
- Knockout matching uses date + time (prevents cross-assignment)
- E2E: random matches validated against live Wikipedia

## Important constraints

- `matches.json` NEVER contains score fields — those live in `scores.json`
- `update_knockout.py` only modifies teams that are placeholders (`is_placeholder()`) — never overwrites real team names
- Knockout matching uses date + local time to differentiate multiple matches on same day
- Pre-commit hook runs all tests before allowing commits
- Calendar refresh interval is 6 hours (PT6H in .ics)

## Wikipedia parsing notes

- Parser: `lxml` (required — `html.parser` fails to find `footballbox` divs)
- Match structure: `div.footballbox` containing `.fleft` (date/time), `.fevent` (teams/score), `.fright` (venue)
- Date is in `span.bday` inside `.fdate`
- Time is in `.ftime` (12h format like "6:00 p.m." — converted via `parse_time_12h()`)
- Knockout page has all matches inside a bracket TABLE, not separated by H2 headings — stage classified by date ranges

## Rollback procedures

**Corrupted matches.json:** `python fetch_matches.py` (re-scrapes Wikipedia, restores placeholders)
**Corrupted scores.json:** `echo '{}' > scores.json` (scores rebuild on next API call)
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
