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
    {"name": "Addis International Bank S.C", "swift": "ABSCETAA", "url": "https://exchange.addisfortune.news/bank/addis-bank-sc-1"},
    {"name": "Ahadu Bank S.C", "swift": "AHUUETAA", "url": "https://exchange.addisfortune.news/bank/ahadu-bank-sc"},
    {"name": "Amhara Bank S.C", "swift": "AMHRETAA", "url": "https://www.amharabank.com/daily-exchange-rate/"},
    {"name": "Awash Bank S.C", "swift": "AWINETAA", "url": "https://exchange.addisfortune.news/bank/awash-bank-sc"},
    {"name": "Bank of Abyssinia", "swift": "ABYSETAA", "url": "https://www.bankofabyssinia.com/exchange-rate-2/"},
    {"name": "Berhan Bank S.C.", "swift": "BERHETAA", "url": "https://exchange.addisfortune.news/bank/berhan-international-bank-sc"},
    {"name": "Bunna International Bank", "swift": "BUNAETAA", "url": "https://bunnabanksc.com/foreign-exchange/"},
    {"name": "Commercial Bank of Ethiopia", "swift": "CBETETAA", "url": "https://exchange.addisfortune.news/bank/commercial-bank-of-ethiopia"},
    {"name": "Cooperative Bank of Oromia S.C.", "swift": "CBORETAA", "url": "https://coopbankoromia.com.et/daily-exchange-rates/"},
    {"name": "Dashen Bank S.C", "swift": "DASHETAA", "url": "https://dashenbanksc.com/daily-exchange-rate/"},
    {"name": "Enat Bank S.C", "swift": "ENATETAA", "url": "https://exchange.addisfortune.news/bank/enat-bank-sc"},
    {"name": "Gadaa Bank S.C", "swift": "GDAAETAA", "url": "https://exchange.addisfortune.news/bank/gadaa-bank-sc"},
    {"name": "Global Bank Ethiopia S.C", "swift": "DEGAETAA", "url": "https://exchange.addisfortune.news/bank/global-bank-ethiopia-sc"},
    {"name": "Hibret Bank S.C. (United Bank)", "swift": "UNTDETAA", "url": "https://www.hibretbank.com.et/hibret-banks-daily-exchange-rate/"},
    {"name": "Lion International Bank S.C", "swift": "LIBSETAA", "url": "https://exchange.addisfortune.news/bank/anbesa-bank-1"},
    {"name": "National Bank of Ethiopia", "swift": "NBETETAA", "url": "https://exchange.addisfortune.news/bank/national-bank-of-ethiopia"},
    {"name": "Nib International Bank S.C", "swift": "NIBIETAA", "url": "https://www.nibbanksc.com/exchange-rate/"},
    # Several banks publish rates only as images/JS that can't be read, so
    # those use the Addis Fortune+ comparison site (robots.txt allows it).
    {"name": "Oromia International Bank S.C", "swift": "ORIRETAA", "url": "https://exchange.addisfortune.news/bank/oromia-international-bank-sc"},
    {"name": "Wegagen Bank S.C", "swift": "WEGAETAA", "url": "https://www.wegagen.com/exchange-rate-cash-notes/"},
    {"name": "Zemen Bank S.C", "swift": "ZEMEETAA", "url": "https://exchange.addisfortune.news/bank/zemen-bank-sc"},
]

NUM_RE = re.compile(r"^-?\d+(\.\d{2,4})?$")

# Parallel/"black market" USD/ETB rate — informal street rate, not an
# official bank or exchange quote. ethioblackmarket.com is a live
# peer-to-peer trading board (its own buyers/sellers posting actual
# deals, with a Telegram group behind it) — its traffic is almost
# entirely from Ethiopia itself, unlike generic multi-country rate
# aggregators, which is the best signal available that this is the
# rate actually used/trusted locally rather than a generic SEO page.
# Still unofficial/unverified, so shown on the page clearly labeled as
# such. (An earlier version of this pointed at egcurrency.com, whose
# "black market" number turned out to barely differ from its own bank
# rate — not a plausible parallel-market premium — so it was dropped.)
BLACK_MARKET_URL = "https://ethioblackmarket.com/"
BLACK_MARKET_SOURCE_NAME = "ethioblackmarket.com"

# The page doesn't publish a simple buy/sell pair — it's a live order
# book, with individual buyer/seller posts at their own prices, rolled
# up into one live rate plus a rolling 24h range and % change
# (confirmed by rendering the real page):
#   OPEN            187.3635
#   CLOSE           187.3862
#   RANGE           187.06 - 187.90
#   DAILY           +0.28%
#   ...
#   187.88
#   Rate:
#   1 USD = 187.88 ETB
BLACK_MARKET_RATE_RE = re.compile(r"Rate:\s*\n?\s*1 USD = ([\d,]+\.?\d*) ETB", re.IGNORECASE)
BLACK_MARKET_RANGE_RE = re.compile(r"RANGE\s*\n\s*([\d,]+\.?\d*)\s*-\s*([\d,]+\.?\d*)", re.IGNORECASE)
BLACK_MARKET_DAILY_RE = re.compile(r"DAILY\s*\n\s*([+-]?[\d.]+)\s*%", re.IGNORECASE)


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
    """Fetch the informal USD/ETB "black market" rate from
    ethioblackmarket.com (a peer-to-peer trading board, not a bank or
    exchange quote — unofficial and unverified, so callers should
    always label it clearly as such). Like most of the bank sites, its
    numbers are rendered by JS after load, so this needs the same
    headless-browser-plus-wait approach as scrape_bank()."""
    try:
        text = ""
        for _attempt in range(2):  # the live board sometimes renders late; retry once
            page.goto(BLACK_MARKET_URL, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            try:
                # wait for the live "1 USD = N ETB" line instead of a fixed sleep
                page.wait_for_function("document.body.innerText.includes('1 USD =')", timeout=25_000)
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(1500)
            text = page.inner_text("body")
            if BLACK_MARKET_RATE_RE.search(text):
                break
    except Exception as exc:  # noqa: BLE001
        return {
            "source": BLACK_MARKET_SOURCE_NAME, "url": BLACK_MARKET_URL, "status": "unavailable",
            "reason": f"Could not load the page ({type(exc).__name__})",
            "rate": None, "range_low": None, "range_high": None, "daily_change_pct": None,
        }

    rate_match = BLACK_MARKET_RATE_RE.search(text)
    range_match = BLACK_MARKET_RANGE_RE.search(text)
    daily_match = BLACK_MARKET_DAILY_RE.search(text)

    rate = float(rate_match.group(1).replace(",", "")) if rate_match else None
    range_low = float(range_match.group(1).replace(",", "")) if range_match else None
    range_high = float(range_match.group(2).replace(",", "")) if range_match else None
    daily_change_pct = float(daily_match.group(1)) if daily_match else None

    if rate is None:
        return {
            "source": BLACK_MARKET_SOURCE_NAME, "url": BLACK_MARKET_URL, "status": "unavailable",
            "reason": "Rate wasn't found in a readable format, even after waiting for the page to load",
            "rate": None, "range_low": None, "range_high": None, "daily_change_pct": None,
        }
    return {
        "source": BLACK_MARKET_SOURCE_NAME, "url": BLACK_MARKET_URL, "status": "ok",
        "rate": rate, "range_low": range_low, "range_high": range_high,
        "daily_change_pct": daily_change_pct,
    }


# NBE-licensed independent forex bureaus (https://nbe.gov.et/independent-forex-bureaus/).
# Phones come from the NBE list; rates come from ethiotrade.org/forex-offices,
# which collects the rates the bureaus publish (robots.txt allows crawling).
# "key" is matched against the name ethiotrade.org uses.
FOREX_BUREAUS = [
    {"name": "Ammann Forex Bureau", "key": "ammann", "phone": "0911-22-01-98"},
    {"name": "AYOTAN Forex Bureau", "key": "ayotan", "phone": "0930-25-12-36"},
    {"name": "DBH Forex Bureau", "key": "dbh", "phone": "0913-06-48-30"},
    {"name": "Ethio Forex Bureau", "key": "ethio", "phone": "0911-23-39-88"},
    {"name": "FOUR X Forex Bureau", "key": "four x", "phone": "0974-55-49-50"},
    {"name": "Global Forex Bureau", "key": "global", "phone": "0911-22-32-68"},
    {"name": "Grace General Forex Bureau", "key": "grace general", "phone": "0969-78-78-78"},
    {"name": "Haron Forex Bureau", "key": "haron", "phone": "0911-20-72-82"},
    {"name": "Robust Forex Bureau", "key": "robust", "phone": "0911-24-68-47"},
    {"name": "Rooha Forex Bureau", "key": "rooha", "phone": "0915-99-00-07"},
    {"name": "Saba Forex Bureau", "key": "saba", "phone": None},
    {"name": "Sheba Forex Bureau", "key": "sheba", "phone": "0911-21-39-40"},
    {"name": "Sibrat Forex Bureau", "key": "sibrat", "phone": "0917-55-16-11"},
    {"name": "Taypay Forex Bureau", "key": "taypay", "phone": "0915-75-20-67"},
    {"name": "Walia Forex Bureau", "key": "walia", "phone": "0967-21-77-77"},
    {"name": "Yoga Forex Bureau", "key": "yoga", "phone": "0982-77-77-70"},
]
FOREX_BUREAU_URL = "https://ethiotrade.org/forex-offices"
BUREAU_ROW_RE = re.compile(r"([A-Za-z][A-Za-z .&-]*? Forex Bureau)\s+(\d{2,3}\.\d{2})\s+(\d{2,3}\.\d{2})")


def scrape_forex_bureaus(page):
    found = {}
    reason = None
    try:
        page.goto(FOREX_BUREAU_URL, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        page.wait_for_timeout(WAIT_SECONDS * 1000)
        try:  # the page lists 10 by default; expand to all
            page.get_by_text("Show all", exact=False).first.click(timeout=3000)
            page.wait_for_timeout(1500)
        except Exception:  # noqa: BLE001
            pass
        text = page.inner_text("body")
        for name, buy, sell in BUREAU_ROW_RE.findall(text):
            key = name.lower().replace(" forex bureau", "").strip()
            b, s_ = float(buy), float(sell)
            if 1 < b < 100000 and 1 < s_ < 100000:
                found.setdefault(key, {"buy": b, "sell": s_})
    except Exception as exc:  # noqa: BLE001
        reason = f"Could not load the page ({type(exc).__name__})"

    out = []
    for bureau in FOREX_BUREAUS:
        usd = found.get(bureau["key"])
        item = {"name": bureau["name"], "phone": bureau["phone"], "url": FOREX_BUREAU_URL,
                "status": "ok" if usd else "unavailable", "usd": usd}
        if not usd:
            item["reason"] = reason or "No published rate found"
        out.append(item)
    return out


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
        print("Scraping forex bureaus...", file=sys.stderr)
        forex_bureaus = scrape_forex_bureaus(page)
        browser.close()

    now = datetime.now(timezone.utc)
    payload = {
        "fetched_at": int(now.timestamp()),
        "fetched_at_iso": now.isoformat(),
        "from_cache": False,
        "source": "playwright",
        "banks": results,
        "black_market": black_market,
        "forex_bureaus": forex_bureaus,
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