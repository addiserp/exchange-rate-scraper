"""TEMP: dump nav links of stockmarket data hub."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context().new_page()
    for u in ["https://data.stockmarket.et/", "https://exchange.addisfortune.news/robots.txt"]:
        r = pg.goto(u, timeout=30000, wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        print("\n#### ", u, r.status)
        if u.endswith("robots.txt"):
            print(pg.inner_text("body")[:800])
        else:
            for t,h in pg.evaluate("[...document.querySelectorAll('a')].map(a=>[a.innerText.trim().slice(0,40), a.href])"):
                print("LINK", t, "|", h)
    b.close()
