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
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

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
        page.goto(server)

        # Login
        page.wait_for_selector("#login-modal", state="visible")
        page.fill("#board-id-input", "test_board_a33f7059")
        username = f"user_{uuid.uuid4()}"
        page.fill("#nickname-input", username)
        page.fill("#password-input", "password123")
        page.click("#register-btn")

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
        assert (
            initial_vpt[4] != new_vpt[4] or initial_vpt[5] != new_vpt[5]
        ), "Viewport should have changed after clicking minimap"

        # Test toggle minimap button
        page.click("#btn-toggle-minimap")
        page.wait_for_timeout(200)
        assert not minimap_container.is_visible()

        page.click("#btn-toggle-minimap")
        page.wait_for_timeout(200)
        assert minimap_container.is_visible()

        browser.close()
