import os
import threading
import time
import uuid
import socket

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from src.main import app

os.environ["TESTING"] = "1"

@pytest.fixture(scope="module")
def test_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)
    yield port
    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.skipif("CI" in os.environ, reason="Playwright tests are skipped in CI")
def test_add_ellipse(test_server: int):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{test_server}")

        board_id = f"board-{uuid.uuid4().hex[:8]}"
        username = f"user-{uuid.uuid4().hex[:8]}"
        password = "password123"

        page.fill("#board-id-input", board_id)
        page.fill("#nickname-input", username)
        page.fill("#password-input", password)
        page.click("#register-btn")

        page.wait_for_selector("#toolbar", state="visible")

        # Click the add ellipse button
        page.evaluate('document.getElementById("btn-ellipse").click()')

        time.sleep(1) # wait for enlivenObjects and render

        # Check properties of the drawn object
        objects_count = page.evaluate("canvas.getObjects().length")
        assert objects_count > 0, "An ellipse should have been drawn"

        ellipse_props = page.evaluate("""
            () => {
                const ellipse = canvas.getObjects()[0];
                return {
                    type: ellipse.type,
                    fill: ellipse.fill,
                    rx: ellipse.rx,
                    ry: ellipse.ry
                };
            }
        """)

        assert ellipse_props["type"] == "ellipse"
        assert ellipse_props["rx"] == 50
        assert ellipse_props["ry"] == 30
        assert ellipse_props["fill"].lower().replace(" ", "") in ["pink", "#ffc0cb", "rgb(255,192,203)"]

        browser.close()
