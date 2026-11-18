"""TEMP: per-bank scrape status + aggregator bank links."""
import sys, json
sys.path.insert(0, "scripts")
import scrape_rates as sr
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    pg = ctx.new_page()
    print("\n#### AGGREGATOR LINKS")
    pg.goto("https://exchange.addisfortune.news/banks", timeout=30000, wait_until="domcontentloaded"); pg.wait_for_timeout(6000)
    links = pg.evaluate("[...document.querySelectorAll('a[href*=\"/bank/\"]')].map(a=>[a.innerText.trim().split('\\n')[0], a.getAttribute('href')])")
    seen=set()
    for t,h in links:
        if h not in seen: seen.add(h); print("LINK", t, "|", h)
    print("\n#### CURRENT SCRAPER STATUS")
    for bank in sr.BANKS:
        r = sr.scrape_bank(pg, bank)
        print("BANK", bank["name"], "|", r["status"], "|", (r.get("usd") or {}), "|", (r.get("reason") or "")[:80])
    b.close()
