import os
import socket
import threading
import uuid

import pytest
import uvicorn

os.environ["TESTING"] = "1"
from src.main import app


@pytest.fixture(scope="module")
def server_url():
    # Setup test server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="critical")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
def test_dark_mode_toggle(server_url):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(server_url)

        # Login
        username = str(uuid.uuid4())
        page.fill("#board-id-input", "darkmode-test")
        page.fill("#nickname-input", username)
        page.fill("#password-input", "testpass")
        page.click("#register-btn")

        # Wait for toolbar
        page.wait_for_selector("#toolbar:not(.hidden)")

        # Initial checks
        body_class = page.evaluate("document.body.className")
        assert "dark-mode" not in body_class
        btn_text = page.locator("#btn-dark-mode").inner_text()
        assert btn_text == "Dark Mode"
        canvas_bg = page.evaluate("window.canvas.backgroundColor")
        assert canvas_bg == "#f5f5f5"

        # Toggle Dark Mode
        page.click("#btn-dark-mode")

        # Assert Dark Mode
        body_class = page.evaluate("document.body.className")
        assert "dark-mode" in body_class
        btn_text = page.locator("#btn-dark-mode").inner_text()
        assert btn_text == "Light Mode"
        canvas_bg = page.evaluate("window.canvas.backgroundColor")
        assert canvas_bg == "#121212"

        # Toggle Light Mode
        page.click("#btn-dark-mode")

        # Assert Light Mode
        body_class = page.evaluate("document.body.className")
        assert "dark-mode" not in body_class
        btn_text = page.locator("#btn-dark-mode").inner_text()
        assert btn_text == "Dark Mode"
        canvas_bg = page.evaluate("window.canvas.backgroundColor")
        assert canvas_bg == "#f5f5f5"

        browser.close()
