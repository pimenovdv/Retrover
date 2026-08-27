import os
import threading
import time
import uuid

import pytest
import uvicorn

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


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skipping UI tests in CI due to missing browser dependencies.",
)
def test_minimap(server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001")

        # Login
        page.fill("#board-id-input", "test_board")
        username = f"user_{uuid.uuid4()}"
        page.fill("#nickname-input", username)
        page.fill("#password-input", "password123")
        page.click("#register-btn")

        # Wait for canvas to load
        page.wait_for_selector("#canvas-container", state="visible")

        # Add a shape
        page.evaluate('document.getElementById("btn-rect").click()')
        page.wait_for_timeout(500)  # Wait for shape to be added and rendered

        # Ensure minimap is visible
        minimap_container = page.locator("#minimap-container")
        assert minimap_container.is_visible()

        # Get viewport initially
        initial_vpt = page.evaluate("window.canvas.viewportTransform")

        # Click on minimap to pan
        page.evaluate("""
            const e = new MouseEvent("mousedown", {
                clientX: document.getElementById("minimap-container").getBoundingClientRect().left + 150,
                clientY: document.getElementById("minimap-container").getBoundingClientRect().top + 100,
                bubbles: true
            });
            document.getElementById("minimap-container").dispatchEvent(e);
            const e2 = new MouseEvent("mouseup", { bubbles: true });
            window.dispatchEvent(e2);
        """)
        page.wait_for_timeout(500)

        # Get viewport after click
        new_vpt = page.evaluate("window.canvas.viewportTransform")

        # Verify viewport changed (panned)
        assert (
            initial_vpt[4] != new_vpt[4] or initial_vpt[5] != new_vpt[5]
        ), "Viewport should have changed after clicking minimap"

        browser.close()
