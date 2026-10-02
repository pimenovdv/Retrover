from playwright.sync_api import sync_playwright
import os

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(f"file://{os.path.abspath('test_event.html')}")

    page.on("console", lambda msg: print(f"Browser console: {msg.text}"))

    page.evaluate("""() => {
        const el = document.getElementById('prop-stroke');
        el.value = '#ff0000';
        el.dispatchEvent(new Event('change'));
        el.dispatchEvent(new Event('input'));
    }""")

    browser.close()
