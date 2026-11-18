"""TEMP: probe bureau rate sources."""
from playwright.sync_api import sync_playwright
URLS = [
 ("https://ethiotrade.org/forex-offices", 4500, True),
 ("https://ethiotrade.org/robots.txt", 1200, False),
 ("https://ethiotrade.org/data", 3500, False),
 ("https://exchange.addisfortune.news/robots.txt", 3000, False),
 ("https://www.capitalmarketethiopia.com/robots.txt", 800, False),
 ("https://data.stockmarket.et/directory", 300, True),
]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context().new_page()
    for u, n, links in URLS:
        try:
            r = pg.goto(u, timeout=40000, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
            print("\n#### ", u, r.status if r else None)
            print(pg.inner_text("body")[:n])
            if links:
                for t,h in pg.evaluate("[...document.querySelectorAll('a')].map(a=>[a.innerText.trim().replace(/\\n/g,' ').slice(0,40), a.href])")[:70]:
                    print("LINK", t, "|", h)
        except Exception as e:
            print("ERR", u, e)
    b.close()
