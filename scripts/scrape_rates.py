#!/usr/bin/env python3
"""
scrape_rates.py — headless-browser exchange-rate scraper for AddisERP's
exchange-rate.html page.

WHY THIS EXISTS
----------------
api/exchange-rates.php fetches each bank's page with plain PHP curl,
which never runs JavaScript. Most Ethiopian bank sites load their rate
table via JavaScript a second or two AFTER the page itself finishes
loading, so curl only ever sees a "Loading..." placeholder for those
banks. There is no way to fix that from PHP alone — curl cannot run
JS no matter how long you make it wait.

This script uses a real (headless) Chromium browser via Playwright,
which DOES run each page's JavaScript, waits a few seconds for the
rate widgets to populate, then reads the actual rendered numbers.
It writes its results to data/exchange-rates-cache.json — the exact
same file api/exchange-rates.php already reads from — so nothing on
the PHP/frontend side has to change to benefit from this.

HOW TO RUN IT
-------------
One-off:
    python3 scripts/scrape_rates.py

On a schedule (recommended — every 10 minutes), add a crontab entry:
    */10 * * * * cd /path/to/addiserp-site-new && /usr/bin/python3 scripts/scrape_rates.py >> /tmp/scrape_rates.log 2>&1

SETUP (one-time, on the machine that will run this — your local
Ubuntu box for testing, or a VPS for production; NOT typical shared
PHP hosting, which can't run Chromium):
    pip install --break-system-packages playwright beautifulsoup4
    python3 -m playwright install --with-deps chromium
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SITE_ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = SITE_ROOT / "data" / "exchange-rates-cache.json"

# How long to wait after a page "loads" for its JS-driven rate widget
# to populate, before we read the DOM. Bump this up if a bank still
# shows "Unavailable" — some are just slower than others.
WAIT_SECONDS = 5
PAGE_TIMEOUT_MS = 25_000

BANKS = [
    {"name": "Abay Bank S.C", "url": "https://exchange.addisfortune.news/bank/abay-bank-sc"},
    {"name": "Addis International Bank S.C", "url": "https://www.addisbanksc.com/"},
    {"name": "Ahadu Bank S.C", "url": "https://exchange.addisfortune.news/bank/ahadu-bank-sc"},
    {"name": "Amhara Bank S.C", "url": "https://www.amharabank.com/daily-exchange-rate/"},
    {"name": "Awash Bank S.C", "url": "https://awashbank.com/exchange-historical/"},
    {"name": "Bank of Abyssinia", "url": "https://www.bankofabyssinia.com/exchange-rate-2/"},
    {"name": "Berhan Bank S.C.", "url": "https://berhanbanksc.com/exchange-rates/"},
    {"name": "Bunna International Bank", "url": "https://bunnabanksc.com/foreign-exchange/"},
    {"name": "Commercial Bank of Ethiopia", "url": "https://combanketh.et/exchange-rates?srcPage=home"},
    {"name": "Cooperative Bank of Oromia S.C.", "url": "https://coopbankoromia.com.et/daily-exchange-rates/"},
    {"name": "Dashen Bank S.C", "url": "https://dashenbanksc.com/daily-exchange-rate/"},
    {"name": "Enat Bank S.C", "url": "https://www.enatbanksc.com/"},
    {"name": "Gadaa Bank S.C", "url": "https://gadaabank.com.et/foreign-exchange-remittances/"},
    {"name": "Global Bank Ethiopia S.C", "url": "https://www.globalbankethiopia.com/remittance-forex/"},
    {"name": "Hibret Bank S.C. (United Bank)", "url": "https://www.hibretbank.com.et/hibret-banks-daily-exchange-rate/"},
    {"name": "Lion International Bank S.C", "url": "https://exchange.addisfortune.news/bank/anbesa-bank-1"},
    {"name": "National Bank of Ethiopia", "url": "https://nbe.gov.et/"},
    {"name": "Nib International Bank S.C", "url": "https://www.nibbanksc.com/exchange-rate/"},
    # Oromia International Bank's site disallows automated access via
    # robots.txt — we don't fetch it at all, out of respect for that,
    # same as api/exchange-rates.php.
    {"name": "Oromia International Bank S.C", "url": "https://oromiabank.com/exchange-rates/",
     "skip": True, "reason": "This bank's site blocks automated access (robots.txt)"},
    {"name": "Wegagen Bank S.C", "url": "https://www.wegagen.com/exchange-rate-cash-notes/"},
    {"name": "Zemen Bank S.C", "url": "https://zemenbank.com/exchange-rates/"},
]

NUM_RE = re.compile(r"^-?\d+(\.\d{2,4})?$")


def extract_currency_rate(html: str, code: str):
    """Same heuristic as the PHP parser: find a table row mentioning the
    currency code, take the first two decimal numbers in that row as
    (buy, sell)."""
    soup = BeautifulSoup(html, "html.parser")
    for row in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not cells:
            continue
        row_text = " | ".join(cells)
        if not re.search(rf"\b{re.escape(code)}\b", row_text, re.IGNORECASE):
            continue
        numbers = []
        for t in cells:
            clean = t.replace(",", "")
            if NUM_RE.match(clean):
                val = float(clean)
                if 1 < val < 100000:
                    numbers.append(val)
        if len(numbers) >= 2:
            return {"buy": numbers[0], "sell": numbers[1]}
    return None


def scrape_bank(page, bank):
    if bank.get("skip"):
        return {
            "name": bank["name"], "url": bank["url"], "status": "unavailable",
            "reason": bank["reason"], "usd": None, "eur": None,
        }
    try:
        page.goto(bank["url"], timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        # Let the page's own JS populate its rate widget.
        page.wait_for_timeout(WAIT_SECONDS * 1000)
        html = page.content()
    except Exception as exc:  # noqa: BLE001 — we want to keep going on any bank failure
        return {
            "name": bank["name"], "url": bank["url"], "status": "unavailable",
            "reason": f"Could not load the page ({type(exc).__name__})", "usd": None, "eur": None,
        }

    usd = extract_currency_rate(html, "USD")
    eur = extract_currency_rate(html, "EUR")

    if not usd and not eur:
        return {
            "name": bank["name"], "url": bank["url"], "status": "unavailable",
            "reason": "Rate wasn't found in a readable format, even after waiting for the page to load",
            "usd": None, "eur": None,
        }
    return {"name": bank["name"], "url": bank["url"], "status": "ok", "usd": usd, "eur": eur}


def main():
    started = time.time()
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
                        "AddisERP-RateWidget/1.0 (+https://www.addiserp.com/exchange-rate.html)")
        )
        page = context.new_page()
        for bank in BANKS:
            print(f"Scraping {bank['name']}...", file=sys.stderr)
            results.append(scrape_bank(page, bank))
        browser.close()

    now = datetime.now(timezone.utc)
    payload = {
        "fetched_at": int(now.timestamp()),
        "fetched_at_iso": now.isoformat(),
        "from_cache": False,
        "source": "playwright",
        "banks": results,
    }

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to a temp file then os.replace() over the
    # real file, so a reader can never see a half-written file.
    tmp_path = CACHE_FILE.with_suffix(CACHE_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2))
    tmp_path.replace(CACHE_FILE)

    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"Done in {time.time() - started:.1f}s — {ok_count}/{len(results)} banks live. "
          f"Wrote {CACHE_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
