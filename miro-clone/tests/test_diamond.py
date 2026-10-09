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
def test_add_diamond(test_server: int):
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

        # Click the add diamond button
        page.evaluate('document.getElementById("btn-diamond").click()')

        time.sleep(1) # wait for enlivenObjects and render

        # Check properties of the drawn path
        objects_count = page.evaluate("canvas.getObjects().length")
        assert objects_count > 0, "A diamond should have been drawn"

        diamond_props = page.evaluate("""
            () => {
                const diamond = canvas.getObjects()[0];
                return {
                    type: diamond.type,
                    fill: diamond.fill,
                    points: diamond.points
                };
            }
        """)

        assert diamond_props["type"] == "polygon"

        # Verify points structure
        assert diamond_props["points"] == [
            {"x": 50, "y": 0},
            {"x": 100, "y": 50},
            {"x": 50, "y": 100},
            {"x": 0, "y": 50}
        ]
        assert diamond_props["fill"].lower().replace(" ", "") in ["orange", "#ffa500", "rgb(255,165,0)"]

        browser.close()
