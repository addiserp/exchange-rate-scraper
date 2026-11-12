import sys
from playwright.sync_api import sync_playwright

URLS = [
    "https://ethioblackmarket.com/",
    "https://ethioblackmarket.com/usd-etb",
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    )
    page = context.new_page()
    for url in URLS:
        print(f"=== {url} ===")
        try:
            resp = page.goto(url, timeout=20000, wait_until="domcontentloaded")
            print(f"status: {resp.status if resp else 'None'}")
            page.wait_for_timeout(5000)
            text = page.inner_text("body")
            print(text[:2500])
        except Exception as exc:
            print(f"ERROR: {type(exc).__name__}: {exc}")
        print("=== END ===")
    browser.close()
