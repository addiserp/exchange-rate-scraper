"""TEMP: probe bureau rate sources."""
from playwright.sync_api import sync_playwright
URLS = [
 ("https://exchange.addisfortune.news/robots.txt", 600),
 ("https://ethiotrade.org/", 6000),
 ("https://ammannforexbureau.com/", 1500),
 ("https://www.capitalmarketethiopia.com/rooha-forex-bureau-exchange-rate-today/", 1500),
 ("https://www.capitalmarketethiopia.com/category/exchange/forex-bureau/", 2500),
 ("https://exchange.et/", 200),
]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context().new_page()
    for u, n in URLS:
        try:
            r = pg.goto(u, timeout=40000, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
            print("\n#### ", u, r.status if r else None)
            print(pg.inner_text("body")[:n])
            if "ethiotrade" in u or "forex-bureau/" in u:
                for t,h in pg.evaluate("[...document.querySelectorAll('a')].map(a=>[a.innerText.trim().slice(0,40), a.href])")[:80]:
                    print("LINK", t, "|", h)
        except Exception as e:
            print("ERR", u, e)
    b.close()
