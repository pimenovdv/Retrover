import os
import socket
import sys
import threading
import uuid

import pytest
import uvicorn
from playwright.async_api import async_playwright

# Ensure the src directory is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import app


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def server_url():
    port = get_free_port()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_lasso(server_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        import time

        for _ in range(10):
            try:
                await page.goto(server_url)
                break
            except Exception:
                time.sleep(1)

        # Register and login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", "test_board_lasso")
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        # Wait for the canvas to be ready
        await page.wait_for_selector("#canvas-container", state="visible")

        # Create two objects via UI
        await page.evaluate('document.getElementById("btn-rect").click()')
        await page.wait_for_timeout(100)

        # Position them
        await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            objs[objs.length-1].set({ left: 100, top: 100 });
            window.canvas.requestRenderAll();
        }""")

        await page.evaluate('document.getElementById("btn-circle").click()')
        await page.wait_for_timeout(100)
        await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            objs[objs.length-1].set({ left: 300, top: 100 });
            window.canvas.requestRenderAll();
        }""")

        # Click lasso button
        await page.evaluate('document.getElementById("btn-lasso").click()')

        # Verify isDrawingMode is on
        is_drawing_mode = await page.evaluate("window.canvas.isDrawingMode")
        assert is_drawing_mode is True

        # Simulate a lasso path around the first object (rect) but not the second (circle)
        # Note: path.path coordinates for freehand paths are absolute coordinates
        await page.evaluate("""() => {
            const pathData = 'M 50 50 L 200 50 L 200 200 L 50 200 Z'; // Encloses (100, 100)
            const path = new fabric.Path(pathData, { fill: '', stroke: 'black' });
            window.canvas.fire('path:created', { path: path });
        }""")

        # The lasso logic should have grouped the rect into an ActiveSelection but keep drawing mode ON
        is_drawing_mode_after = await page.evaluate("window.canvas.isDrawingMode")
        assert is_drawing_mode_after is True

        active_objects_len = await page.evaluate(
            "window.canvas.getActiveObjects().length"
        )
        assert active_objects_len == 1

        await browser.close()
