# FIFA World Cup 2026 — Calendar Subscription

Subscribe to all FIFA World Cup 2026 matches directly on your phone or email client. Free, auto-updated with scores.

## How to Subscribe

Copy the calendar URL:

```
https://marceloingarano.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics
```

### iPhone (Apple Calendar)
1. Settings → Calendar → Accounts → Add Account
2. Select "Other" → Add Subscribed Calendar
3. Paste the URL → Subscribe

### Android (Google Calendar)
1. Open Google Calendar on web (calendar.google.com)
2. Settings → Add calendar → From URL
3. Paste the URL → Add calendar

### Outlook
1. Calendar → Add calendar → Subscribe from web
2. Paste the URL → Import

## Event Format

```
Title:  🇧🇷 Brasil vs Marrocos 🇲🇦 — Grupo C       (before match)
Title:  🇧🇷 Brasil 2 x 0 Marrocos 🇲🇦 — Grupo C   (with score)
Local:  MetLife Stadium, East Rutherford, EUA
Notes:  FIFA World Cup 2026 — Grupo C
        Jogo #7
        🕐 18:00 (ET)
        📺 Globo / CazéTV
        🔗 https://...
```

## Architecture

```
matches.json          ← Static schedule (teams, dates, stadiums, TV, streaming)
scores.json           ← Dynamic scores only (updated via API or manually)
generate_calendar.py  → Merges both → generates .ics
```

## Development

### Setup
```bash
pip install -r requirements.txt
```

### Fetch match schedule (from Wikipedia)
```bash
python fetch_matches.py           # All 104 matches
python fetch_matches.py --groups  # Group stage only
python fetch_matches.py --knockout # Knockout only
```

### Update scores
```bash
python update_scores.py              # Fetch from API
python update_scores.py --match 7    # Specific match
python update_scores.py --manual 7 2 0  # Manual: match 7, home 2, away 0
```

### Generate calendar
```bash
python generate_calendar.py
```

The `.ics` file is generated in `docs/` — GitHub Pages serves from this folder.

## Hosting

GitHub Pages serves from `/docs` on branch `main`.
Live at: https://marceloingarano.github.io/fifa-worldcup-2026-calendar/
