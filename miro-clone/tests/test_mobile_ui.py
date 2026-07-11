import os

os.environ["TESTING"] = "1"

import threading
import time
import pytest
import uvicorn
import asyncio
from fastapi import FastAPI
import sys

# Ensure src is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(scope="module")
def server():
    from src.main import app

    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(1) # wait for server to start
    yield
    # No explicit shutdown needed for daemon thread in test suite

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
def test_mobile_ui_layout(server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        # Simulate mobile device
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={'width': 375, 'height': 667},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X)'
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8002")

        page.fill("#board-id-input", "mobile_board")
        page.fill("#nickname-input", "mobile_user")
        page.click("#join-btn")

        page.wait_for_selector("#toolbar", state="visible")

        # Check toolbar flex-wrap
        toolbar_wrap = page.evaluate("window.getComputedStyle(document.getElementById('toolbar')).flexWrap")
        assert toolbar_wrap == "wrap", "Toolbar should wrap on mobile"

        # Check properties panel is positioned at top or similarly responsive
        props_top = page.evaluate("window.getComputedStyle(document.getElementById('properties-panel')).top")
        assert props_top != "auto", "Properties panel should be positioned relative to top on mobile"

        browser.close()
