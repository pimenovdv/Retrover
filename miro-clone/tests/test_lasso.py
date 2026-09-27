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
async def test_lasso_tool(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(test_server)

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        board_id = f"test_board_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", board_id)
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "testpass")
        await page.click("#register-btn")

        # Wait for canvas to be visible
        await page.wait_for_selector("#canvas-container", state="visible")

        # Add objects
        rect1_id = f"rect1_{uuid.uuid4().hex[:8]}"
        rect2_id = f"rect2_{uuid.uuid4().hex[:8]}"
        circ1_id = f"circ1_{uuid.uuid4().hex[:8]}"

        await page.evaluate(f"""
            window.canvas.add(new fabric.Rect({{ id: '{rect1_id}', left: 100, top: 100, width: 50, height: 50 }}));
            window.canvas.add(new fabric.Rect({{ id: '{rect2_id}', left: 200, top: 100, width: 50, height: 50 }}));
            window.canvas.add(new fabric.Circle({{ id: '{circ1_id}', left: 400, top: 400, radius: 25 }}));
            window.canvas.requestRenderAll();
        """)

        # Wait for objects to be added
        await page.wait_for_timeout(500)

        await page.evaluate("""
            window.canvas.discardActiveObject();
            window.canvas.requestRenderAll();
        """)

        # Activate lasso
        await page.evaluate('document.getElementById("btn-lasso")?.click()')

        # Simulate drawing a lasso path that encompasses rect1 and rect2 but not circ1
        # Rect1 is at (100, 100) -> center (125, 125)
        # Rect2 is at (200, 100) -> center (225, 125)
        # We need points in polygon
        # Create a programmatic path on the canvas to trigger path:created
        await page.evaluate("""
            const path = new fabric.Path('M 0 0 L 300 0 L 300 200 L 0 200 z');
            path.path = [['M', 0, 0], ['L', 300, 0], ['L', 300, 200], ['L', 0, 200]];
            window.canvas.fire('path:created', { path: path });
        """)

        await page.wait_for_timeout(1000) # wait for path:created logic to run

        # Verify active selection
        selection_info = await page.evaluate("""
            (() => {
                const obj = window.canvas.getActiveObject();
                if (!obj) return [];
                if (obj.type === 'activeSelection') {
                    return obj.getObjects().map(o => o.id);
                }
                return [obj.id];
            })()
        """)

        print("Selection Info:", selection_info)
        assert selection_info is not None, "No active selection was made"
        assert rect1_id in selection_info, "Rect1 was not selected"
        assert rect2_id in selection_info, "Rect2 was not selected"
        assert circ1_id not in selection_info, "Circle was incorrectly selected"

        await browser.close()
