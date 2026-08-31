import asyncio
import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn

os.environ["TESTING"] = "1"

from src.database import Base, engine
from src.main import app


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


async def _init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="module", autouse=True)
def setup_database_and_server():
    asyncio.run(_init_db())
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)

    yield port

    server.should_exit = True
    thread.join(timeout=2)
    asyncio.run(_drop_db())


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
def test_smart_guides(setup_database_and_server):
    port = setup_database_and_server
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{port}")

        # Register and join
        page.fill("#board-id-input", "guides-board")
        page.fill("#nickname-input", str(uuid.uuid4()))
        page.fill("#password-input", "testpass")
        page.click("#register-btn")
        page.wait_for_selector("#canvas-container", state="visible")

        # Turn on Smart Guides
        page.check("#chk-smart-guides")

        # Add two rectangles
        page.click("#btn-rect")
        page.wait_for_timeout(100)
        page.click("#btn-rect")
        page.wait_for_timeout(100)

        # Position the first rect
        page.evaluate("""
            const objs = window.canvas.getObjects();
            objs[0].set({ left: 100, top: 100, width: 100, height: 100 });
            objs[1].set({ left: 300, top: 300, width: 100, height: 100 });
            window.canvas.renderAll();
        """)

        # Simulate moving the second rect near the first rect
        # X: left edge to left edge
        page.evaluate("""
            const objs = window.canvas.getObjects();
            const movingObj = objs[1];
            movingObj.set({ left: 105, top: 300 }); // within threshold of 10
            movingObj.setCoords();
            window.canvas.fire('object:moving', { target: movingObj });
        """)

        # Assert snapped
        left_after = page.evaluate("window.canvas.getObjects()[1].left")
        assert left_after == 100, f"Expected 100, got {left_after}"

        # Turn off Smart Guides
        page.uncheck("#chk-smart-guides")

        page.evaluate("""
            const objs = window.canvas.getObjects();
            const movingObj = objs[1];
            movingObj.set({ left: 105, top: 300 }); // within threshold of 10
            movingObj.setCoords();
            window.canvas.fire('object:moving', { target: movingObj });
        """)

        left_after_disabled = page.evaluate("window.canvas.getObjects()[1].left")
        assert left_after_disabled == 105, f"Expected 105, got {left_after_disabled}"

        browser.close()
