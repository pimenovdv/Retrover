import pytest
from playwright.async_api import async_playwright
import uvicorn
import asyncio
import threading
import socket
import uuid
import json
from src.main import app

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture(scope="module")
def server_url():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    def run_server():
        asyncio.run(server.serve())

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"

    # Wait for server to start
    import time
    time.sleep(1)

    yield url

    server.should_exit = True
    thread.join(timeout=2)

@pytest.mark.asyncio
async def test_add_pentagon(server_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        test_board_id = f"test_board_{uuid.uuid4().hex[:8]}"
        await page.goto(f"{server_url}/")

        # Login
        await page.fill('#board-id-input', test_board_id)
        await page.fill('#nickname-input', 'tester')
        await page.fill('#password-input', 'password')
        await page.click('#register-btn')

        # Wait for canvas
        await page.wait_for_function("window.canvas !== undefined")

        # Click add pentagon button
        await page.evaluate('document.getElementById("btn-pentagon").click()')

        # Check objects on canvas
        objects = await page.evaluate("() => { return window.canvas.getObjects().map(o => o.toObject()); }")

        pentagon_objects = [obj for obj in objects if obj.get('type') == 'polygon' and len(obj.get('points', [])) == 5]
        assert len(pentagon_objects) == 1

        pentagon = pentagon_objects[0]
        assert pentagon['fill'] == 'orange'

        await browser.close()