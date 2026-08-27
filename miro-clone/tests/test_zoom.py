import os
import threading
import time
import uuid

import pytest
import uvicorn

# We must set TESTING=1 so that the backend knows to use a local or in-memory DB if configured,
# or avoid starting side-effects, though this test mainly cares about the frontend state.
os.environ["TESTING"] = "1"

from src.main import app


@pytest.fixture(scope="module")
def test_server():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)  # Wait for server to start
    yield port
    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_zoom_controls(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"http://127.0.0.1:{test_server}/")

        # Login
        await page.fill("#board-id-input", "zoom_test_board")
        username = f"user_{uuid.uuid4()}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Give it a tiny bit of time for initialization
        await page.wait_for_timeout(500)

        # Ensure buttons are visible
        await page.wait_for_selector("#btn-zoom-in", state="visible")

        # Test Zoom In button
        initial_zoom = await page.evaluate("window.canvas.getZoom()")
        assert initial_zoom == 1.0, "Initial zoom should be 1.0"

        # We need to evaluate click instead of page.click because buttons might be pushed out or have pointer issues
        await page.evaluate('document.getElementById("btn-zoom-in").click()')
        await page.wait_for_timeout(200)

        zoom_in = await page.evaluate("window.canvas.getZoom()")
        assert zoom_in > initial_zoom, f"Zoom should increase, got {zoom_in}"

        # Test Zoom Out button
        await page.evaluate('document.getElementById("btn-zoom-out").click()')
        await page.wait_for_timeout(200)

        zoom_out = await page.evaluate("window.canvas.getZoom()")
        assert zoom_out < zoom_in, f"Zoom should decrease, got {zoom_out}"

        # Reset zoom
        # Pan a little first to test viewport reset
        await page.evaluate("""() => {
            let vpt = window.canvas.viewportTransform;
            vpt[4] = 100; // pan x
            vpt[5] = 100; // pan y
            window.canvas.setViewportTransform(vpt);
        }""")
        vpt_before = await page.evaluate("() => window.canvas.viewportTransform")
        assert vpt_before[4] == 100

        await page.evaluate('document.getElementById("btn-zoom-reset").click()')
        await page.wait_for_timeout(200)

        zoom_reset = await page.evaluate("window.canvas.getZoom()")
        assert zoom_reset == 1.0, f"Zoom should reset to 1.0, got {zoom_reset}"

        vpt_after = await page.evaluate("() => window.canvas.viewportTransform")
        assert vpt_after[4] == 0
        assert vpt_after[5] == 0

        # Test Keyboard Shortcut Zoom In (Ctrl + =)
        await page.keyboard.press("Control+=")
        await page.wait_for_timeout(200)
        zoom_in_kbd = await page.evaluate("window.canvas.getZoom()")
        assert (
            zoom_in_kbd > 1.0
        ), f"Zoom should increase via keyboard, got {zoom_in_kbd}"

        # Test Keyboard Shortcut Zoom Out (Ctrl + -)
        await page.keyboard.press("Control+-")
        await page.wait_for_timeout(200)
        zoom_out_kbd = await page.evaluate("window.canvas.getZoom()")
        assert (
            zoom_out_kbd < zoom_in_kbd
        ), f"Zoom should decrease via keyboard, got {zoom_out_kbd}"

        # Test Keyboard Shortcut Reset Zoom (Ctrl + 0)
        await page.keyboard.press("Control+0")
        await page.wait_for_timeout(200)
        zoom_reset_kbd = await page.evaluate("window.canvas.getZoom()")
        assert (
            zoom_reset_kbd == 1.0
        ), f"Zoom should reset to 1.0 via keyboard, got {zoom_reset_kbd}"

        await browser.close()
