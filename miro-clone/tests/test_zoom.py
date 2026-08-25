import os
import uuid

import pytest

os.environ["TESTING"] = "1"


@pytest.fixture
def test_server():
    import threading
    import time

    import uvicorn

    from src.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8002, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)
    yield server
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_zoom_controls(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8002/")

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Initial zoom should be 1
        initial_zoom = await page.evaluate("() => window.canvas.getZoom()")
        assert initial_zoom == 1

        # Zoom in
        await page.click("#btn-zoom-in")
        await page.wait_for_timeout(100)
        zoom_in_val = await page.evaluate("() => window.canvas.getZoom()")
        assert zoom_in_val > 1
        assert abs(zoom_in_val - 1.2) < 0.01

        # Zoom out
        await page.click("#btn-zoom-out")
        await page.wait_for_timeout(100)
        zoom_out_val = await page.evaluate("() => window.canvas.getZoom()")
        assert abs(zoom_out_val - 1) < 0.01

        await page.click("#btn-zoom-out")
        await page.wait_for_timeout(100)
        zoom_out_val2 = await page.evaluate("() => window.canvas.getZoom()")
        assert zoom_out_val2 < 1

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

        await page.click("#btn-zoom-reset")
        await page.wait_for_timeout(100)

        final_zoom = await page.evaluate("() => window.canvas.getZoom()")
        assert final_zoom == 1

        vpt_after = await page.evaluate("() => window.canvas.viewportTransform")
        assert vpt_after[4] == 0
        assert vpt_after[5] == 0

        await browser.close()
