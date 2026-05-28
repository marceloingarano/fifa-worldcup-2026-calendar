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

Each event shows:
```
🇧🇷 Brazil vs 🇷🇸 Serbia (2-0)
📍 MetLife Stadium, East Rutherford, USA
```

## Development

### Setup
```bash
pip install -r requirements.txt
```

### Update match data
```bash
python fetch_matches.py          # Fetch schedule from sources
python fetch_matches.py --scores # Update scores
```

### Generate calendar
```bash
python generate_calendar.py
```

The `.ics` file is generated in `docs/` — GitHub Pages serves from this folder.

### Update scores
Edit `matches.json` — set `score_home` and `score_away` for completed matches, then re-run `generate_calendar.py`.

## Hosting (GitHub Pages)

1. Push this repo to GitHub
2. Go to Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, folder: `/docs`
3. Your calendar will be live at `https://<username>.github.io/fifa-worldcup-2026-calendar/fifa-worldcup-2026.ics`
