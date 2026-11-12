import sys
from playwright.sync_api import sync_playwright

URL = "https://egcurrency.com/en/currency/USD-to-ETB/blackMarket"

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    )
    page = context.new_page()
    page.goto(URL, timeout=25000, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    text = page.inner_text("body")
    browser.close()

print("=== BODY TEXT (first 3000 chars) ===")
print(text[:3000])
print("=== END ===", file=sys.stderr)
