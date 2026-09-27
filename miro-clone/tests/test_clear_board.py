import os
import threading
import time
import uuid

import pytest
import uvicorn

os.environ["TESTING"] = "1"

from src.main import app


@pytest.fixture(scope="module")
def test_server():
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


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_clear_board(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(test_server)

        # Login
        await page.fill("#board-id-input", f"clear_board_test_{uuid.uuid4()}")
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
        await page.mouse.move(300, 300)
        await page.mouse.up()
        await page.wait_for_timeout(200)

        # Draw a circle
        await page.click("#btn-circle")
        await page.mouse.move(400, 400)
        await page.mouse.down()
        await page.mouse.move(500, 500)
        await page.mouse.up()
        await page.wait_for_timeout(200)

        # Verify shapes exist
        objects = await page.evaluate("() => window.canvas.getObjects().length")
        assert objects == 2

        # Setup dialog handler to accept confirm
        page.on("dialog", lambda dialog: dialog.accept())

        # Click Clear Board
        await page.click("#btn-clear-board")
        await page.wait_for_timeout(500)

        # Verify board is empty
        objects_after = await page.evaluate("() => window.canvas.getObjects().length")
        assert objects_after == 0

        # Undo the clear board
        await page.click("#btn-undo")
        await page.wait_for_timeout(500)

        # Verify objects are restored
        objects_restored = await page.evaluate(
            "() => window.canvas.getObjects().length"
        )
        assert objects_restored == 2

        # Redo the clear board
        await page.click("#btn-redo")
        await page.wait_for_timeout(500)

        # Verify board is empty again
        objects_redo = await page.evaluate("() => window.canvas.getObjects().length")
        assert objects_redo == 0

        await browser.close()
