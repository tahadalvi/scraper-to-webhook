"""
scraper-to-webhook
==================

Logs in to a website with a saved browser session, scrapes a results list,
removes duplicates, and POSTs the clean list to a webhook.

Demo target: https://quotes.toscrape.com (a public practice site that accepts
any username/password). Swap the three functions marked CUSTOMISE for a real
site; everything else (session reuse, dedupe, webhook, alerts, logging) stays.

Usage:
    python scraper.py            # normal scheduled run (headless)
    python scraper.py --headed   # first run: watch the browser, session gets saved
    python scraper.py --dry-run  # scrape and print, do not call the webhook
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout, sync_playwright

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

SITE_URL = os.getenv("SITE_URL", "https://quotes.toscrape.com")
SITE_USER = os.getenv("SITE_USER", "demo")
SITE_PASS = os.getenv("SITE_PASS", "demo")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:5005/webhook")
STATE_FILE = ROOT / os.getenv("STATE_FILE", "session_state.json")
LOG_FILE = ROOT / "runs.log"
SCREENSHOT_DIR = ROOT / "screenshots"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("scraper")


# --------------------------------------------------------------------------- #
# CUSTOMISE 1: how to tell whether we are logged in
# --------------------------------------------------------------------------- #
def is_logged_in(page: Page) -> bool:
    page.goto(f"{SITE_URL}/", wait_until="domcontentloaded")
    return page.locator("a[href='/logout']").count() > 0


# --------------------------------------------------------------------------- #
# CUSTOMISE 2: how to log in
# --------------------------------------------------------------------------- #
def login(page: Page) -> None:
    log.info("Logging in as %s", SITE_USER)
    page.goto(f"{SITE_URL}/login", wait_until="domcontentloaded")
    page.fill("#username", SITE_USER)
    page.fill("#password", SITE_PASS)
    page.click("input[type='submit']")
    page.wait_for_selector("a[href='/logout']", timeout=15_000)


# --------------------------------------------------------------------------- #
# CUSTOMISE 3: what to scrape. Return a list of raw strings.
# --------------------------------------------------------------------------- #
def scrape_items(page: Page) -> list[str]:
    """Collect every author name on the first three pages (duplicates included)."""
    items: list[str] = []
    for page_no in range(1, 4):
        page.goto(f"{SITE_URL}/page/{page_no}/", wait_until="domcontentloaded")
        names = page.locator("small.author").all_inner_texts()
        log.info("page %d: %d entries", page_no, len(names))
        items.extend(n.strip() for n in names)
    return items


# --------------------------------------------------------------------------- #
# Generic plumbing below. Usually no changes needed.
# --------------------------------------------------------------------------- #
def dedupe(items: list[str]) -> list[str]:
    """Case-insensitive dedupe, first occurrence wins, order preserved."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def send_webhook(symbols: list[str], dry_run: bool) -> None:
    payload = {
        "source": SITE_URL,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(symbols),
        "items": symbols,
    }
    if dry_run:
        log.info("DRY RUN, would POST to %s:\n%s", WEBHOOK_URL, json.dumps(payload, indent=2))
        return
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=20)
    resp.raise_for_status()
    log.info("Webhook accepted %d items (HTTP %d)", len(symbols), resp.status_code)


def alert(message: str, page: Page | None = None) -> None:
    """Hook for your preferred alert channel (email, Telegram, Slack).

    The demo writes a screenshot and logs at ERROR level. Wire in a real
    notifier here; the bot never tries to bypass CAPTCHAs or security checks.
    """
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    if page is not None:
        shot = SCREENSHOT_DIR / f"alert_{datetime.now():%Y%m%d_%H%M%S}.png"
        try:
            page.screenshot(path=str(shot), full_page=True)
            message += f" (screenshot: {shot.name})"
        except Exception:  # noqa: BLE001
            pass
    log.error("ALERT: %s", message)


def ensure_session(context: BrowserContext, page: Page) -> None:
    if is_logged_in(page):
        log.info("Saved session still valid")
        return
    try:
        login(page)
    except PlaywrightTimeout:
        alert("Login did not complete. A CAPTCHA or security check may be blocking it; log in once manually with --headed.", page)
        raise SystemExit(2)
    context.storage_state(path=str(STATE_FILE))
    log.info("Session saved to %s", STATE_FILE.name)


def run(headed: bool, dry_run: bool) -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        context = browser.new_context(storage_state=str(STATE_FILE) if STATE_FILE.exists() else None)
        page = context.new_page()
        try:
            ensure_session(context, page)
            raw = scrape_items(page)
            clean = dedupe(raw)
            log.info("%d raw entries -> %d unique", len(raw), len(clean))
            send_webhook(clean, dry_run)
            return 0
        except SystemExit as e:
            return int(e.code or 1)
        except Exception as e:  # noqa: BLE001
            alert(f"Run failed: {e!r}", page)
            return 1
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--headed", action="store_true", help="show the browser (use for the first login)")
    ap.add_argument("--dry-run", action="store_true", help="scrape and print, skip the webhook")
    args = ap.parse_args()
    sys.exit(run(headed=args.headed, dry_run=args.dry_run))
