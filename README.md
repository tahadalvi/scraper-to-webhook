# scraper-to-webhook

A small, reliable Python bot that **logs in to a website with a saved session, scrapes a list, removes
duplicates, and POSTs the clean result to a webhook** on a schedule.

This is the pattern behind requests like *"log in to my scanner every morning, grab the symbols, send
them to my trading software"* or *"pull today's leads from the portal and push them to my CRM"*.

The demo targets [quotes.toscrape.com](https://quotes.toscrape.com), a public practice site that accepts
any username and password, so you can run it end to end in two minutes without real credentials.

## What it does

```
saved session? ──yes──> open site ──> scrape pages ──> dedupe ──> POST JSON to webhook
      │ no                                                            │
      └── log in once, save session_state.json ──────────────────────┘
```

- **Session reuse.** Playwright's `storage_state` is saved after the first login and reloaded on every
  run, so the bot normally never sees the login page.
- **Dedupe.** Case-insensitive, order preserving, first occurrence wins.
- **Webhook.** One JSON POST: `{"source", "run_at", "count", "items"}`. Easy to reshape for any API.
- **Alerts instead of workarounds.** If login fails, or a CAPTCHA or security check appears, the bot
  stops, saves a screenshot to `screenshots/`, logs an ERROR, and exits with code 2. It never tries to
  bypass a CAPTCHA. Plug your email, Telegram or Slack notifier into `alert()`.
- **Scheduling.** `schedule_windows.ps1` registers a daily Task Scheduler job; `crontab.example`
  covers Linux and VPS hosts.
- **Logs.** Every run appends to `runs.log`.

## Quick start

```bash
git clone <this repo> && cd scraper-to-webhook
python -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
playwright install chromium
copy .env.example .env            # cp on Linux/macOS
```

Terminal 1, start the local webhook receiver:

```bash
python webhook_receiver.py
```

Terminal 2, run the bot:

```bash
python scraper.py --headed        # first run, watch it log in, session is saved
python scraper.py                 # every run after that, headless
```

The receiver prints the payload and appends it to `received.jsonl`.

## Sample run

```
2026-10-20 15:41:02 INFO Logging in as demo
2026-10-20 15:41:04 INFO Session saved to session_state.json
2026-10-20 15:41:05 INFO page 1: 10 entries
2026-10-20 15:41:05 INFO page 2: 10 entries
2026-10-20 15:41:06 INFO page 3: 10 entries
2026-10-20 15:41:06 INFO 30 raw entries -> 20 unique
2026-10-20 15:41:06 INFO Webhook accepted 20 items (HTTP 200)
```

Webhook payload:

```json
{
  "source": "https://quotes.toscrape.com",
  "run_at": "2026-10-20T10:11:06+00:00",
  "count": 20,
  "items": ["Albert Einstein", "J.K. Rowling", "Jane Austen", "..."]
}
```

## Adapting it to your site

Only three functions in `scraper.py` know anything about the target site. Each is marked `CUSTOMISE`:

| Function | Job |
|---|---|
| `is_logged_in(page)` | Return True when the saved session still works |
| `login(page)` | Fill the login form once |
| `scrape_items(page)` | Return the raw list of strings to send |

Everything else, session handling, dedupe, webhook, alerts, logging and scheduling, stays as is.

## Configuration

All settings live in `.env` (see `.env.example`). Credentials never go in code or in git.

| Variable | Meaning |
|---|---|
| `SITE_URL` | Base URL of the site |
| `SITE_USER`, `SITE_PASS` | Login details, used only when the saved session has expired |
| `WEBHOOK_URL` | Where the JSON is POSTed |
| `STATE_FILE` | Where the browser session is stored |

## Notes

- Automating a login to a third-party site may be restricted by that site's terms of service. Check
  before running this against a production account.
- Exit codes: `0` success, `1` unexpected error, `2` login blocked (manual login needed).

## Licence

MIT
