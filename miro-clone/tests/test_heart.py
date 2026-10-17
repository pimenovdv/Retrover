import pytest
from playwright.async_api import async_playwright
import uuid
import uvicorn
import os
import asyncio
import threading
import socket
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
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to start
    import time
    time.sleep(2)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()

@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_add_heart(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Generate a unique board ID
        board_id = f"test_board_{uuid.uuid4().hex[:8]}"
        await page.goto(f"{test_server}?board={board_id}")

        # Fill in nickname and enter board
        await page.fill("#nickname-input", "testuser")
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        # Wait for the canvas and toolbar
        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_function("window.canvas !== undefined")
        await page.wait_for_selector("#toolbar", state="visible")

        # Click the Add Heart button
        await page.evaluate('document.getElementById("btn-heart").click()')

        await asyncio.sleep(0.5)

        # Wait for canvas to update and check if the heart is added
        heart_count = await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            return objs.filter(o => o.type === 'path').length;
        }""")

        assert heart_count == 1, "Expected exactly one heart on the canvas"

        await browser.close()
