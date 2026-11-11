#!/usr/bin/env python3

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
    {"name": "Abay Bank S.C", "swift": "ABAYETAA", "url": "https://exchange.addisfortune.news/bank/abay-bank-sc"},
    {"name": "Addis International Bank S.C", "swift": "ABSCETAA", "url": "https://www.addisbanksc.com/"},
    {"name": "Ahadu Bank S.C", "swift": "AHUUETAA", "url": "https://exchange.addisfortune.news/bank/ahadu-bank-sc"},
    {"name": "Amhara Bank S.C", "swift": "AMHRETAA", "url": "https://www.amharabank.com/daily-exchange-rate/"},
    {"name": "Awash Bank S.C", "swift": "AWINETAA", "url": "https://awashbank.com/exchange-historical/"},
    {"name": "Bank of Abyssinia", "swift": "ABYSETAA", "url": "https://www.bankofabyssinia.com/exchange-rate-2/"},
    {"name": "Berhan Bank S.C.", "swift": "BERHETAA", "url": "https://berhanbanksc.com/exchange-rates/"},
    {"name": "Bunna International Bank", "swift": "BUNAETAA", "url": "https://bunnabanksc.com/foreign-exchange/"},
    {"name": "Commercial Bank of Ethiopia", "swift": "CBETETAA", "url": "https://combanketh.et/exchange-rates?srcPage=home"},
    {"name": "Cooperative Bank of Oromia S.C.", "swift": "CBORETAA", "url": "https://coopbankoromia.com.et/daily-exchange-rates/"},
    {"name": "Dashen Bank S.C", "swift": "DASHETAA", "url": "https://dashenbanksc.com/daily-exchange-rate/"},
    {"name": "Enat Bank S.C", "swift": "ENATETAA", "url": "https://www.enatbanksc.com/"},
    {"name": "Gadaa Bank S.C", "swift": "GDAAETAA", "url": "https://gadaabank.com.et/foreign-exchange-remittances/"},
    {"name": "Global Bank Ethiopia S.C", "swift": "DEGAETAA", "url": "https://www.globalbankethiopia.com/remittance-forex/"},
    {"name": "Hibret Bank S.C. (United Bank)", "swift": "UNTDETAA", "url": "https://www.hibretbank.com.et/hibret-banks-daily-exchange-rate/"},
    {"name": "Lion International Bank S.C", "swift": "LIBSETAA", "url": "https://exchange.addisfortune.news/bank/anbesa-bank-1"},
    {"name": "National Bank of Ethiopia", "swift": "NBETETAA", "url": "https://nbe.gov.et/"},
    {"name": "Nib International Bank S.C", "swift": "NIBIETAA", "url": "https://www.nibbanksc.com/exchange-rate/"},
    # Oromia International Bank's site disallows automated access via
    # robots.txt — we don't fetch it at all, out of respect for that,
    # same as api/exchange-rates.php.
    {"name": "Oromia International Bank S.C", "swift": "ORIRETAA", "url": "https://oromiabank.com/exchange-rates/",
     "skip": True, "reason": "This bank's site blocks automated access (robots.txt)"},
    {"name": "Wegagen Bank S.C", "swift": "WEGAETAA", "url": "https://www.wegagen.com/exchange-rate-cash-notes/"},
    {"name": "Zemen Bank S.C", "swift": "ZEMEETAA", "url": "https://zemenbank.com/exchange-rates/"},
]

NUM_RE = re.compile(r"^-?\d+(\.\d{2,4})?$")

# Parallel/"black market" USD/ETB rate — informal street rate, not an
# official bank or exchange quote. No bank, exchange or financial data
# vendor (incl. TradingView) actually tracks this; egcurrency.com is a
# dedicated tracker for it. Its numbers are unverified/unofficial, so
# this is shown on the page clearly labeled as such.
BLACK_MARKET_URL = "https://egcurrency.com/en/currency/USD-to-ETB/blackMarket"
BLACK_MARKET_SOURCE_NAME = "egcurrency.com"

# e.g. "...at Black Market, Tuesday, 04.08.2026 11:18\n\n160.22"
BLACK_MARKET_BUY_RE = re.compile(
    r"Black Market[^\n]*\n+\s*([\d,]+\.\d+)", re.IGNORECASE
)
# e.g. "Sell Price: 158.62 -0.12 Compared to yesterday's last price"
BLACK_MARKET_SELL_RE = re.compile(
    r"Sell Price:\s*([\d,]+\.\d+)", re.IGNORECASE
)


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
    swift = bank.get("swift")
    if bank.get("skip"):
        return {
            "name": bank["name"], "swift": swift, "url": bank["url"], "status": "unavailable",
            "reason": bank["reason"], "usd": None, "eur": None,
        }
    try:
        page.goto(bank["url"], timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        # Let the page's own JS populate its rate widget.
        page.wait_for_timeout(WAIT_SECONDS * 1000)
        html = page.content()
    except Exception as exc:  # noqa: BLE001 — we want to keep going on any bank failure
        return {
            "name": bank["name"], "swift": swift, "url": bank["url"], "status": "unavailable",
            "reason": f"Could not load the page ({type(exc).__name__})", "usd": None, "eur": None,
        }

    usd = extract_currency_rate(html, "USD")
    eur = extract_currency_rate(html, "EUR")

    if not usd and not eur:
        return {
            "name": bank["name"], "swift": swift, "url": bank["url"], "status": "unavailable",
            "reason": "Rate wasn't found in a readable format, even after waiting for the page to load",
            "usd": None, "eur": None,
        }
    return {"name": bank["name"], "swift": swift, "url": bank["url"], "status": "ok", "usd": usd, "eur": eur}


def scrape_black_market(page):
    """Fetch the informal USD/ETB "black market" rate from egcurrency.com.
    This is not a bank or exchange quote — it's an unofficial, unverified
    street-rate tracker, so callers should always label it clearly as
    such. Like most of the bank sites, its numbers are rendered by JS
    after load, so this needs the same headless-browser-plus-wait
    approach as scrape_bank()."""
    try:
        page.goto(BLACK_MARKET_URL, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(WAIT_SECONDS * 1000)
        text = page.inner_text("body")
    except Exception as exc:  # noqa: BLE001
        return {
            "source": BLACK_MARKET_SOURCE_NAME, "url": BLACK_MARKET_URL, "status": "unavailable",
            "reason": f"Could not load the page ({type(exc).__name__})", "buy": None, "sell": None,
        }

    buy_match = BLACK_MARKET_BUY_RE.search(text)
    sell_match = BLACK_MARKET_SELL_RE.search(text)
    buy = float(buy_match.group(1).replace(",", "")) if buy_match else None
    sell = float(sell_match.group(1).replace(",", "")) if sell_match else None

    if buy is None and sell is None:
        return {
            "source": BLACK_MARKET_SOURCE_NAME, "url": BLACK_MARKET_URL, "status": "unavailable",
            "reason": "Rate wasn't found in a readable format, even after waiting for the page to load",
            "buy": None, "sell": None,
        }
    return {
        "source": BLACK_MARKET_SOURCE_NAME, "url": BLACK_MARKET_URL, "status": "ok",
        "buy": buy, "sell": sell,
    }


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

        print("Scraping black-market USD/ETB rate...", file=sys.stderr)
        black_market = scrape_black_market(page)
        browser.close()

    now = datetime.now(timezone.utc)
    payload = {
        "fetched_at": int(now.timestamp()),
        "fetched_at_iso": now.isoformat(),
        "from_cache": False,
        "source": "playwright",
        "banks": results,
        "black_market": black_market,
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