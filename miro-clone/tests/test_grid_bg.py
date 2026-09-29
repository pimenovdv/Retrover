import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn
from playwright.async_api import async_playwright

os.environ["TESTING"] = "1"
from src.main import app


def run_server(server):
    server.run()


@pytest.fixture(scope="module")
def test_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    time.sleep(2)
    os.makedirs("uploads", exist_ok=True)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join()


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_grid_background_toggle(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(test_server)

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", "grid_bg_board")
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "pass123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Verify initial background color is string
        bg_color_initial = await page.evaluate("() => window.canvas.backgroundColor")
        assert isinstance(bg_color_initial, str)
        assert bg_color_initial == "#f5f5f5"

        # Enable grid background
        await page.check("#chk-grid-bg")
        await page.wait_for_timeout(500)

        # Verify background color is an object (Pattern)
        bg_pattern_enabled = await page.evaluate("""() => {
            const bg = window.canvas.backgroundColor;
            if (bg && typeof bg === 'object' && bg.source) {
                return true;
            }
            return false;
        }""")
        assert bg_pattern_enabled is True

        # Disable grid background
        await page.uncheck("#chk-grid-bg")
        await page.wait_for_timeout(500)

        # Verify background color reverts to string
        bg_color_disabled = await page.evaluate("() => window.canvas.backgroundColor")
        assert isinstance(bg_color_disabled, str)
        assert bg_color_disabled == "#f5f5f5"

        await browser.close()