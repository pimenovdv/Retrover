import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn
from playwright.async_api import async_playwright

from src.main import app


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def test_server():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()

    time.sleep(1)  # Wait for server to start

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_delete_selected_objects(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(test_server)

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", "default")
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "testpass")
        await page.click("#register-btn")

        # Wait for canvas to be visible
        await page.wait_for_selector("#canvas-container", state="visible")

        # Add a rectangle
        await page.evaluate("""
            const rect = new fabric.Rect({
                left: 100,
                top: 100,
                width: 50,
                height: 50,
                fill: 'red',
                id: `test-rect-${window.uuidv4()}`
            });
            window.canvas.add(rect);
            window.canvas.requestRenderAll();
        """)

        # Wait for object to be fully processed by canvas
        await page.wait_for_timeout(500)

        # Verify object is added
        count_before = await page.evaluate(
            "window.canvas.getObjects().filter(o => !o.is_background).length"
        )
        assert count_before >= 1

        # Select the object programmatically
        await page.evaluate("""
            const objs = window.canvas.getObjects().filter(o => !o.is_background);
            const obj = objs[objs.length - 1];
            window.canvas.setActiveObject(obj);
            window.canvas.requestRenderAll();
        """)

        # Wait for UI to update
        await page.wait_for_timeout(500)

        # Click Delete button
        await page.evaluate('document.getElementById("btn-delete")?.click()')

        # Wait for UI to update
        await page.wait_for_timeout(500)

        # Verify object is removed
        count_after = await page.evaluate(
            "window.canvas.getObjects().filter(o => !o.is_background).length"
        )
        assert count_after == count_before - 1

        await browser.close()
