import pytest
import os

os.environ["TESTING"] = "1"
import asyncio
from httpx import AsyncClient
from src.main import app
from src.database import get_db, engine, Base
from src.models import Shape
import json

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup test DB
    import sqlite3
    if os.path.exists("test.db"):
        os.remove("test.db")
    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(init_db())
    yield
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.mark.asyncio
async def test_eraser_adds_path_with_gco():
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        # Create a WebSocket connection
        with client.websocket_connect("/ws/default/testuser") as ws:
            # Send an 'add' action for an eraser path
            path_data = {
                "id": "path1",
                "type": "path",
                "left": 10,
                "top": 10,
                "globalCompositeOperation": "destination-out"
            }
            ws.send_json({
                "action": "add",
                "object": path_data
            })

            # Wait a moment for DB save
            import time
            time.sleep(0.1)

    async for db in get_db():
        shape = await db.get(Shape, "path1")
        assert shape is not None
        assert shape.type == "path"
        assert "globalCompositeOperation" in shape.properties
        assert shape.properties["globalCompositeOperation"] == "destination-out"
        break

# Skip UI test if CI because we don't install browsers there
@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI")
def test_eraser_ui():
    from playwright.sync_api import sync_playwright
    import threading
    import uvicorn
    import time

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="error"))
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    time.sleep(1) # wait for server to start

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://127.0.0.1:8001/")

            # join board
            page.fill("#nickname-input", "testuser")
            page.click("#join-btn")

            # Check drawing mode initially
            page.wait_for_function("() => window.canvas && window.canvas.isDrawingMode === false")

            # Click eraser
            page.click("#btn-eraser")

            # Verify window.isErasing is true and canvas.isDrawingMode is true
            is_erasing = page.evaluate("() => window.isErasing")
            assert is_erasing is True

            is_drawing_mode = page.evaluate("() => window.canvas.isDrawingMode")
            assert is_drawing_mode is True

            # Click freehand
            page.click("#btn-freehand")

            # Verify window.isErasing is false and canvas.isDrawingMode is true
            is_erasing = page.evaluate("() => window.isErasing")
            assert is_erasing is False

            is_drawing_mode = page.evaluate("() => window.canvas.isDrawingMode")
            assert is_drawing_mode is True

            browser.close()
    finally:
        server.should_exit = True
        thread.join()
