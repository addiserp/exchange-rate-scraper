"""TEMP"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    for u in ("https://ethiotrade.org/banks","https://ethioblackmarket.com/"):
        pg.goto(u, timeout=40000, wait_until="domcontentloaded")
        try: pg.wait_for_function("document.body.innerText.includes('1 USD =')||document.body.innerText.includes('You get')", timeout=20000)
        except Exception: pass
        pg.wait_for_timeout(3000)
        print("\n####", u); print(pg.inner_text("body")[:3500] if "banks" in u else pg.inner_text("body")[-900:])
    b.close()
