import asyncio
import os
import threading
import pytest
import uvicorn
import time

# Set TESTING environment variable before importing app modules
os.environ["TESTING"] = "1"

from src.main import app

@pytest.fixture(scope="module")
def server():
    # Run the server in a background thread
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()

    # Wait for server to start
    time.sleep(1)

    yield

    # Teardown
    server.should_exit = True
    thread.join()

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI due to missing browser dependencies.")
def test_minimap(server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001")

        # Login
        page.fill("#board-id-input", "test_board")
        page.fill("#nickname-input", "tester")
        page.click("#join-btn")

        # Wait for canvas to load
        page.wait_for_selector("#canvas-container", state="visible")

        # Add a shape
        page.click("#btn-rect")
        page.wait_for_timeout(500)  # Wait for shape to be added and rendered

        # Ensure minimap is visible
        minimap_container = page.locator("#minimap-container")
        assert minimap_container.is_visible()

        # Get viewport initially
        initial_vpt = page.evaluate("window.canvas.viewportTransform")

        # Click on minimap to pan
        minimap_container.click(position={"x": 150, "y": 100})
        page.wait_for_timeout(500)

        # Get viewport after click
        new_vpt = page.evaluate("window.canvas.viewportTransform")

        # Verify viewport changed (panned)
        assert initial_vpt[4] != new_vpt[4] or initial_vpt[5] != new_vpt[5], "Viewport should have changed after clicking minimap"

        browser.close()
