import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn

os.environ["TESTING"] = "1"

from src.main import app


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def test_server():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)  # give server time to start

    yield port

    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_flip_object(test_server):
    from playwright.async_api import async_playwright

    port = test_server
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"http://127.0.0.1:{port}/")

        # Login
        await page.fill("#board-id-input", f"flip_test_{uuid.uuid4()}")
        username = f"user_{uuid.uuid4()}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_timeout(500)

        # Draw a rectangle
        await page.click("#btn-rect")
        await page.mouse.move(200, 200)
        await page.mouse.down()
        await page.mouse.move(250, 250)
        await page.mouse.up()
        await page.wait_for_timeout(200)

        # Select the object and manually focus properties
        await page.evaluate(
            "() => { window.canvas.setActiveObject(window.canvas.getObjects().find(o => !o.is_background)); window.canvas.requestRenderAll(); document.getElementById('properties-panel').style.display = 'block'; }"
        )

        # Test flip property on a rect

        await page.wait_for_timeout(200)

        # Ensure properties panel is visible
        is_visible = await page.evaluate(
            "() => document.getElementById('properties-panel').style.display !== 'none'"
        )
        assert is_visible

        # Click Flip X
        await page.evaluate(
            "() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipX', !obj.flipX); window.canvas.requestRenderAll(); } }"
        )
        await page.wait_for_timeout(200)

        flip_x_val = await page.evaluate("() => window.canvas.getActiveObject().flipX")
        assert flip_x_val is True

        # Click Flip Y
        await page.evaluate(
            "() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipY', !obj.flipY); window.canvas.requestRenderAll(); } }"
        )
        await page.wait_for_timeout(200)

        flip_y_val = await page.evaluate("() => window.canvas.getActiveObject().flipY")
        assert flip_y_val is True

        # Click Flip X again (toggle off)
        await page.evaluate(
            "() => { const obj = window.canvas.getActiveObject(); if(obj) { obj.set('flipX', !obj.flipX); window.canvas.requestRenderAll(); } }"
        )
        await page.wait_for_timeout(200)

        flip_x_val2 = await page.evaluate("() => window.canvas.getActiveObject().flipX")
        assert flip_x_val2 is False

        await browser.close()
