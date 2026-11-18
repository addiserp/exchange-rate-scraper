"""TEMP"""
import re
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("https://ethiotrade.org/banks", timeout=40000, wait_until="domcontentloaded"); pg.wait_for_timeout(6000)
    try: pg.get_by_text("Show all", exact=False).first.click(timeout=3000); pg.wait_for_timeout(1500)
    except Exception as e: print("noclick", e)
    t = pg.inner_text("body")
    for m in re.finditer(r"\n\t?([A-Za-z][^\n\t]*?)\t(\d{2,3}\.\d{2})\t(\d{2,3}\.\d{2})\t", t): print("ROW", m.groups())
    pg.goto("https://ethioblackmarket.com/", timeout=40000, wait_until="domcontentloaded")
    try: pg.wait_for_function("document.body.innerText.includes('1 USD =')", timeout=25000)
    except Exception: pass
    m = re.search(r"1 USD = ([\d.,]+) ETB", pg.inner_text("body")); print("BM", m and m.group(1))
    b.close()
