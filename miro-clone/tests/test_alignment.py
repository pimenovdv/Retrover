import asyncio
import os
import threading
import uuid
import pytest
from playwright.sync_api import sync_playwright

os.environ["TESTING"] = "1"

import uvicorn
from fastapi.testclient import TestClient

from src.database import Base, engine
from src.main import app

def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8002, log_level="info")
    server = uvicorn.Server(config)
    server.run()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="module")
def test_server():
    asyncio.run(init_db())
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    import time
    time.sleep(1) # wait for server to start
    yield
    # We can't easily kill uvicorn server thread cleanly here without keeping a reference to it
    # But as it's a daemon thread, it will die when the test process dies.
    asyncio.run(drop_db())

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI due to Playwright missing dependencies")
def test_alignment(test_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        test_username = f"testuser_{uuid.uuid4().hex}"
        page.goto("http://127.0.0.1:8002/?board=alignment_board")

        page.wait_for_selector('#login-modal', state='visible')
        page.fill('#nickname-input', test_username)
        page.fill('#password-input', 'password123')
        page.click('#register-btn')
        page.wait_for_selector('#login-modal', state='hidden')

        # Add a couple of rectangles
        page.click('#btn-rect')
        page.wait_for_timeout(500)

        page.click('#btn-rect')
        page.wait_for_timeout(500)

        # We need to select them and align them
        page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    const objs = canvas.getObjects();
                    // Just move the second one so they are not perfectly aligned
                    objs[1].set({ left: 300, top: 300 });
                    objs[1].setCoords();
                    canvas.renderAll();

                    const sel = new fabric.ActiveSelection(objs, { canvas: canvas });
                    canvas.setActiveObject(sel);
                    canvas.renderAll();
                    resolve();
                });
            }
        """)

        # Wait a moment for rendering and event handlers
        page.wait_for_timeout(500)

        # Click align center
        page.click('#btn-align-center')
        page.wait_for_timeout(500)

        # Verify alignment
        result = page.evaluate("""
            () => {
                const objs = canvas.getObjects();
                // We aligned center, so their left values should be equal
                // Let's check left property of all non-background objects
                const shapes = objs.filter(o => !o.is_background);
                return shapes.map(o => o.left);
            }
        """)

        assert len(result) >= 2
        # Center alignment aligns them such that they have the same center relative to the group
        # Wait, if we aligned them center in ActiveSelection, their absolute lefts will be the same if they have the same width.
        # But we made sure they are both rects with default width (100). So their lefts should be equal.
        assert result[0] == result[1], f"Objects were not center aligned. Lefts: {result}"

        browser.close()
