import asyncio
import json
import logging
import os
import threading
import time

import pytest
import uvicorn

# We must set TESTING=1 so that the backend knows to use a local or in-memory DB if configured,
# or avoid starting side-effects, though this test mainly cares about the frontend state.
os.environ["TESTING"] = "1"

from src.main import app

def run_server():
    # Run the uvicorn server in a separate thread
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.run()

@pytest.fixture(scope="module")
def test_server():
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(2)  # Wait for server to start
    yield
    # No direct clean way to stop uvicorn in a thread easily without modifying it,
    # but since thread is daemon=True, it will die with the process.

@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI")
async def test_background_image(test_server):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto("http://127.0.0.1:8000/")

        # Login
        await page.fill("#board-id-input", "bg_test_board")
        await page.fill("#nickname-input", "TestUser")
        await page.click("#join-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Wait a bit for WS connection and init
        await page.wait_for_timeout(500)

        # Clear background first just in case
        await page.click("#btn-clear-bg")
        await page.wait_for_timeout(200)

        # Create a dummy image file to upload
        dummy_img_path = "tests/dummy.png"
        if not os.path.exists("tests"):
            os.makedirs("tests")
        with open(dummy_img_path, "wb") as f:
            # Minimal 1x1 png
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82')

        # Intercept file chooser
        async with page.expect_file_chooser() as fc_info:
            await page.click("#btn-set-bg")
        file_chooser = await fc_info.value
        await file_chooser.set_files(dummy_img_path)

        # Wait for the image to be processed and added to canvas
        await page.wait_for_timeout(2000)

        # Evaluate canvas state to check for background image
        bg_objects = await page.evaluate('''() => {
            return window.canvas.getObjects().filter(o => o.is_background === true).map(o => ({
                is_background: o.is_background,
                selectable: o.selectable,
                evented: o.evented,
                z_index: o.z_index
            }));
        }''')

        assert len(bg_objects) == 1, f"Expected 1 background object, found {len(bg_objects)}"
        bg = bg_objects[0]
        assert bg['is_background'] is True
        assert bg['selectable'] is False
        assert bg['evented'] is False
        assert bg['z_index'] == -9999

        # Now clear the background
        await page.click("#btn-clear-bg")
        await page.wait_for_timeout(1000)

        bg_objects_after = await page.evaluate('''() => {
            return window.canvas.getObjects().filter(o => o.is_background === true);
        }''')
        assert len(bg_objects_after) == 0, "Background should be removed"

        await browser.close()

        if os.path.exists(dummy_img_path):
            os.remove(dummy_img_path)
