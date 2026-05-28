# FIFA World Cup 2026 — Calendar Subscription

All 104 matches on your phone calendar. Free, auto-updated with live scores.

## Subscribe

```
https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics
```

| Platform | How to |
|---|---|
| **iPhone** | Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar → paste URL |
| **Android** | Google Calendar web (desktop mode) → + Other calendars → From URL → paste URL |
| **Outlook** | Calendar → Add calendar → Subscribe from web → paste URL |

## What you get

```
🇧🇷 BRASIL vs Marrocos 🇲🇦 — Grupo C         (before match)
🇧🇷 BRASIL 2 x 0 Marrocos 🇲🇦 — Grupo C     (with score)

Location: MetLife Stadium, East Rutherford, EUA
Notes:    🕐 18:00 (ET) | 📺 CazéTV | 🔗 youtube.com/@CasimiroMiguel
```

- 104 matches with emoji flags and team names in Portuguese
- Scores updated automatically every 10 minutes during matches
- Knockout teams resolved automatically as the tournament progresses
- Calendar syncs every 6 hours on your device

## How it works

```
matches.json       ← Schedule (Wikipedia scrape)
scores.json        ← Live scores (OpenLigaDB API, free, no auth)
generate_calendar  → Merges both → .ics served via GitHub Pages
```

**Automation (GitHub Actions):**
- Scores update every 10min during match hours (Jun 11 – Jul 19)
- Knockout teams resolve daily after group stage ends

## Development

```bash
pip install -r requirements.txt

python fetch_matches.py            # Scrape schedule from Wikipedia
python update_scores.py --live     # Fetch live + final scores
python update_scores.py --final    # Consolidate finished matches only
python update_knockout.py          # Resolve knockout placeholders
python generate_calendar.py        # Regenerate .ics
python -m security.validator       # Validate .ics security

python -m pytest tests/ -v         # Run 152 tests
```

See [OPERATIONS.md](OPERATIONS.md) for full procedures, rollback plans, security details, and automation.
