from playwright.sync_api import sync_playwright
import os
import uuid

def run_cuj(page):
    page.goto("http://127.0.0.1:8000")
    page.wait_for_timeout(500)

    # Login
    username = f"user_{uuid.uuid4().hex[:8]}"
    page.fill("#nickname-input", username)
    page.fill("#password-input", "password")
    page.click("#register-btn")

    page.wait_for_selector("#canvas-container", state="visible")
    page.wait_for_timeout(500)

    # Add Text
    page.click("#btn-text")
    page.wait_for_timeout(1000)

    # Strikethrough it (use evaluate to click it since it might be out of viewport/hidden by another element)
    page.evaluate('document.getElementById("btn-strikethrough").click()')
    page.wait_for_timeout(1000)

    # Take screenshot at the key moment
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    os.makedirs("/home/jules/verification/videos", exist_ok=True)
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
