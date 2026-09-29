from playwright.sync_api import sync_playwright
import os
import uuid
import subprocess
import socket
import time

def run_cuj(page, port):
    page.goto(f"http://127.0.0.1:{port}")
    page.wait_for_timeout(500)

    # Login
    username = f"user_{uuid.uuid4().hex[:8]}"
    page.fill("#nickname-input", username)
    page.fill("#password-input", "password")
    page.click("#register-btn")

    page.wait_for_selector("#canvas-container", state="visible")
    page.wait_for_timeout(500)

    # Grid Toggle
    page.click("#btn-grid-toggle")
    page.wait_for_timeout(1000)

    # Add Sticky Note
    page.click("#btn-sticky")
    page.wait_for_timeout(1000)

    # Change color to green (#CCFFCC)
    page.evaluate('document.querySelector(".sticky-color-btn[data-color=\\"#CCFFCC\\"]").click()')
    page.wait_for_timeout(1000)

    # Take screenshot at the key moment
    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    os.makedirs("/home/jules/verification/videos", exist_ok=True)
    os.makedirs("/home/jules/verification/screenshots", exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()

    server_process = subprocess.Popen(["python", "-m", "uvicorn", "src.main:app", "--port", str(port)])
    time.sleep(2)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir="/home/jules/verification/videos",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            try:
                run_cuj(page, port)
            finally:
                context.close()
                browser.close()
    finally:
        server_process.terminate()
        server_process.wait()
