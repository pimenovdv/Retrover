import os
import threading
import uuid

import pytest
import uvicorn
from playwright.async_api import async_playwright

# Set testing environment variable BEFORE importing app modules
os.environ["TESTING"] = "1"

from src.main import app

# Port for the background server
PORT = 8011


class ServerThread(threading.Thread):
    def __init__(self, app, host, port):
        super().__init__()
        self.server = uvicorn.Server(
            uvicorn.Config(app, host=host, port=port, log_level="error")
        )

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True
        self.join()


@pytest.fixture(scope="module")
def test_server():
    server = ServerThread(app, "127.0.0.1", PORT)
    server.start()
    yield
    server.stop()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skipping UI tests in CI due to missing dependencies",
)
async def test_history_panel(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"http://127.0.0.1:{PORT}/")

        board_id = "test-history-board"
        nickname = f"User-{uuid.uuid4().hex[:6]}"

        await page.fill("#board-id-input", board_id)
        await page.fill("#nickname-input", nickname)
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        # Wait for toolbar to be visible
        await page.wait_for_selector("#toolbar:not(.hidden)", state="visible")

        # History panel should be hidden initially
        history_panel = page.locator("#history-panel")
        assert await history_panel.is_hidden()

        # Add a rectangle to trigger an add action
        await page.evaluate('document.getElementById("btn-rect").click()')

        # Wait for socket to propagate or local state to settle
        await page.wait_for_timeout(500)

        # Open history panel
        await page.evaluate('document.getElementById("btn-history").click()')

        # Check panel is visible
        assert await history_panel.is_visible()

        # Check that 'Action: add' is inside the list
        list_items = page.locator("#history-list li")
        count = await list_items.count()
        assert count > 0, "History list is empty"

        first_item_text = await list_items.nth(0).text_content()
        assert (
            "Action: add" in first_item_text
        ), f"Expected 'Action: add', got '{first_item_text}'"

        await browser.close()
