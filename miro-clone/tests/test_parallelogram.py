import pytest
from playwright.async_api import async_playwright
import uvicorn
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
async def test_add_parallelogram(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Setup board with a dynamic board id
        import uuid

        board_id = f"test_board_{uuid.uuid4().hex[:8]}"
        await page.goto(f"{test_server}/?board={board_id}")

        await page.fill("#nickname-input", "testuser")
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_function("window.canvas !== undefined")

        # Click the Parallelogram button
        await page.evaluate('document.getElementById("btn-parallelogram").click()')

        # Wait a bit for the shape to be added and events to fire
        await asyncio.sleep(0.5)

        # Check if polygon exists on canvas and has expected properties
        parallelogram_count = await page.evaluate("""() => {
            const objects = window.canvas.getObjects();
            return objects.filter(obj => obj.type === 'polygon' && obj.fill === 'lightblue').length;
        }""")

        assert parallelogram_count == 1, (
            "Expected exactly one parallelogram on the canvas"
        )

        await browser.close()
