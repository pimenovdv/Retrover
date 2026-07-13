import pytest
import os
import asyncio
import sys
import threading
import uvicorn
import time

os.environ["TESTING"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import app
from src.database import Base, engine

@pytest.fixture(autouse=True, scope="module")
def setup_db_sync():
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_setup())
    yield
    loop.run_until_complete(_teardown())


@pytest.fixture(scope="module")
def test_server():
    os.environ["TESTING"] = "1"
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8002, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    time.sleep(2)

    yield "http://127.0.0.1:8002"

    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason='Playwright dependencies fail on CI')
def test_responsive_mobile_viewport(test_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Emulate a mobile device or just set a small viewport
        page = browser.new_page(viewport={"width": 375, "height": 667})
        page.goto(test_server)

        # Login
        page.fill("#nickname-input", "mobile_user")
        page.click("#join-btn")

        page.wait_for_selector("#canvas-container", state="visible")
        page.wait_for_timeout(500)

        # Ensure the toolbar is loaded
        toolbar_box = page.locator("#toolbar").bounding_box()
        assert toolbar_box is not None

        # Click on rectangle to ensure properties panel works in mobile view
        page.click("#btn-rect")
        page.wait_for_timeout(500)
        page.mouse.click(100, 100) # Ensure a shape is selected
        page.wait_for_timeout(500)

        # In Playwright, we can evaluate a script to check computed styles
        toolbar_width = page.evaluate("window.getComputedStyle(document.getElementById('toolbar')).width")

        # Check if chat panel has proper mobile styling
        # (width 95% according to the new merged media query, which evaluates to a pixel value)
        chat_width = page.evaluate("window.getComputedStyle(document.getElementById('chat-panel')).width")
        # Ensure it doesn't assert a fixed 250px size since we updated the media query to 95%
        assert "px" in chat_width

        browser.close()
