import pytest
import os
import asyncio
import sys
import threading
import uvicorn
from playwright.sync_api import sync_playwright

import os
import subprocess




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
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    import time
    time.sleep(2)

    yield "http://127.0.0.1:8001"

    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason='Playwright dependencies fail on CI')
def test_undo_redo(test_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(test_server)

        page.fill("#nickname-input", "playwright_user")
        page.click("#join-btn")

        page.wait_for_selector("#canvas-container", state="visible")
        page.wait_for_timeout(500)

        # Click rectangle btn
        page.click("#btn-rect")
        page.wait_for_timeout(500)

        # Let's ensure window.undoStack evaluates correctly or we check another property.
        # We will dispatch keyboard events for undo/redo

        page.keyboard.down('Control')
        page.keyboard.press('z')
        page.keyboard.up('Control')
        page.wait_for_timeout(500)

        page.keyboard.down('Control')
        page.keyboard.press('y')
        page.keyboard.up('Control')
        page.wait_for_timeout(500)

        # Perform undo
        page.click("#btn-undo")
        page.wait_for_timeout(500)

        undo_len = page.evaluate("() => { return window.undoStack ? window.undoStack.length : -1; }")
        assert undo_len == 0

        redo_len = page.evaluate("() => { return window.redoStack ? window.redoStack.length : -1; }")
        assert redo_len == 1

        # Perform redo
        page.click("#btn-redo")
        page.wait_for_timeout(500)

        undo_len = page.evaluate("() => { return window.undoStack ? window.undoStack.length : -1; }")
        assert undo_len == 1

        redo_len = page.evaluate("() => { return window.redoStack ? window.redoStack.length : -1; }")
        assert redo_len == 0

        # Verify canvas items visually restored
        canvas_objects = page.evaluate("() => { return window.canvas ? window.canvas.getObjects().length : -1; }")
        assert canvas_objects > 0

        browser.close()
