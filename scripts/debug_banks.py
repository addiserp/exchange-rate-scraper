"""TEMP"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    for ua in (None, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AddisERP-RateWidget/1.0 (+https://www.addiserp.com/exchange-rate.html)"):
        pg = b.new_context(**({"user_agent": ua} if ua else {})).new_page()
        for u in ("https://ethioblackmarket.com/", "https://ethiotrade.org/black-market"):
            r = pg.goto(u, timeout=40000, wait_until="domcontentloaded"); pg.wait_for_timeout(8000)
            print("\n####", "customUA" if ua else "defaultUA", u, r.status)
            print(pg.inner_text("body")[:1800])
    b.close()
