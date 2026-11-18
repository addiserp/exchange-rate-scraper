"""TEMP: dump rendered text of URLs listed in scripts/debug_urls.txt (one per line, optional |maxchars)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

lines = [l.strip() for l in Path(__file__).with_name("debug_urls.txt").read_text().splitlines() if l.strip()]
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    pg = ctx.new_page()
    for line in lines:
        url, _, n = line.partition("|")
        n = int(n or 3000)
        print(f"\n######## {url}")
        try:
            r = pg.goto(url, timeout=30000, wait_until="domcontentloaded")
            pg.wait_for_timeout(6000)
            print("status:", r.status if r else None, "| title:", pg.title())
            print(pg.inner_text("body")[:n])
        except Exception as e:
            print("ERROR", type(e).__name__, str(e)[:200])
    b.close()
