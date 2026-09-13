import asyncio
import uuid
import socket
import threading
import pytest
from playwright.async_api import async_playwright
import uvicorn

from src.main import app

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture(scope="module")
def test_server():
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time
    time.sleep(1)  # wait for server to start

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=2)

@pytest.mark.asyncio
async def test_panning_spacebar(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(test_server)

        # Login
        test_board = f"board-{uuid.uuid4().hex[:8]}"
        test_user = f"user-{uuid.uuid4().hex[:8]}"
        await page.fill('#board-id-input', test_board)
        await page.fill('#nickname-input', test_user)
        await page.fill('#password-input', 'testpass')
        await page.click('#register-btn')

        # Wait for canvas
        await page.wait_for_selector('#canvas-container', state='visible')

        # Get initial viewport transform
        initial_vpt = await page.evaluate('window.canvas.viewportTransform')
        assert initial_vpt[4] == 0 and initial_vpt[5] == 0

        # Simulate spacebar down
        await page.keyboard.down('Space')

        # Simulate mouse drag
        canvas_box = await page.locator('#canvas-container').bounding_box()
        start_x = canvas_box['x'] + canvas_box['width'] / 2
        start_y = canvas_box['y'] + canvas_box['height'] / 2

        await page.mouse.move(start_x, start_y)
        await page.mouse.down()
        await page.mouse.move(start_x + 100, start_y + 50)
        await page.mouse.up()

        # Simulate spacebar up
        await page.keyboard.up('Space')

        # Check viewport transform
        new_vpt = await page.evaluate('window.canvas.viewportTransform')
        assert new_vpt[4] == 100
        assert new_vpt[5] == 50

        await browser.close()

@pytest.mark.asyncio
async def test_panning_hand_tool(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(test_server)

        # Login
        test_board = f"board-{uuid.uuid4().hex[:8]}"
        test_user = f"user-{uuid.uuid4().hex[:8]}"
        await page.fill('#board-id-input', test_board)
        await page.fill('#nickname-input', test_user)
        await page.fill('#password-input', 'testpass')
        await page.click('#register-btn')

        # Wait for canvas
        await page.wait_for_selector('#canvas-container', state='visible')

        # Get initial viewport transform
        initial_vpt = await page.evaluate('window.canvas.viewportTransform')
        assert initial_vpt[4] == 0 and initial_vpt[5] == 0

        # Enable hand tool using js evaluate to avoid visibility issues
        await page.evaluate('document.getElementById("btn-hand").click()')

        # Check that Hand Mode is active
        is_hand_mode = await page.evaluate('window.isHandMode')
        assert is_hand_mode is True

        # Simulate mouse drag
        canvas_box = await page.locator('#canvas-container').bounding_box()
        start_x = canvas_box['x'] + canvas_box['width'] / 2
        start_y = canvas_box['y'] + canvas_box['height'] / 2

        await page.mouse.move(start_x, start_y)
        await page.mouse.down()
        await page.mouse.move(start_x - 50, start_y - 30)
        await page.mouse.up()

        # Check viewport transform
        new_vpt = await page.evaluate('window.canvas.viewportTransform')
        assert new_vpt[4] == -50
        assert new_vpt[5] == -30

        await browser.close()
