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
    time.sleep(2)

    yield port

    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_select_all_btn(test_server):
    from playwright.async_api import async_playwright

    port = test_server
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"http://127.0.0.1:{port}/")

        # Login
        await page.fill("#board-id-input", f"select_all_{uuid.uuid4()}")
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

        # Draw a circle
        await page.click("#btn-circle")
        await page.mouse.move(300, 300)
        await page.mouse.down()
        await page.mouse.move(350, 350)
        await page.mouse.up()
        await page.wait_for_timeout(200)

        # Draw a background image (should not be selected)
        await page.evaluate("""() => {
            return new Promise((resolve) => {
                const img = new fabric.Image('');
                img.set({is_background: true, selectable: false});
                window.canvas.add(img);
                window.canvas.requestRenderAll();
                resolve();
            });
        }""")

        # Click the "Select All" button via JS to bypass viewport visibility checks
        await page.evaluate('document.getElementById("btn-select-all").click()')
        await page.wait_for_timeout(200)

        active_type = await page.evaluate(
            "() => window.canvas.getActiveObject() ? window.canvas.getActiveObject().type : null"
        )
        assert active_type == "activeSelection"

        sel_count = await page.evaluate(
            "() => window.canvas.getActiveObject().getObjects().length"
        )
        assert sel_count == 2

        await browser.close()
