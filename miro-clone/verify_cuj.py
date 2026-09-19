from playwright.sync_api import sync_playwright, expect
import threading
import time
import uvicorn
from src.main import app
import os
import uuid

os.environ["TESTING"] = "1"

def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8003, log_level="error")
    server = uvicorn.Server(config)
    server.run()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("http://127.0.0.1:8003/")

            # Login
            username = f"user_{uuid.uuid4().hex[:8]}"
            page.fill("#nickname-input", username)
            page.fill("#password-input", "password")
            page.click("#register-btn")

            page.wait_for_selector("#canvas-container", state="visible")

            # Zoom in with kb shortcut
            page.keyboard.press("Control+=")
            time.sleep(0.5)
            page.keyboard.press("Control+=")
            time.sleep(0.5)

            # verify zoom > 1
            zoom_val = page.evaluate("() => window.canvas.getZoom()")
            assert zoom_val > 1

            page.screenshot(path="/home/jules/verification/zoom_verification.png")
            print("Screenshot saved to /home/jules/verification/zoom_verification.png")

        finally:
            browser.close()
