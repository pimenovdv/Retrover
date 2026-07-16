import pytest
import os
import threading
import uvicorn
import asyncio
from fastapi.testclient import TestClient

@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    os.environ["TESTING"] = "1"

@pytest.fixture(scope="module")
def app_server():
    from src.main import app
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8001, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time
    time.sleep(1) # wait for server to start

    yield

    server.should_exit = True
    thread.join()

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI due to browser deps")
def test_copy_paste_playwright(app_server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001/")

        # Login
        page.fill("#board-id-input", "copy_paste_board")
        page.fill("#nickname-input", "playwright_user")
        page.click("#join-btn")

        # Wait for canvas
        page.wait_for_selector("#canvas-container", state="visible")

        # Add a rectangle
        page.click("#btn-rect")
        page.wait_for_timeout(1000) # give it time to render and send WS

        # Select the newly added rectangle
        # We can evaluate to select it
        page.evaluate("""() => {
            const canvas = window.canvas;
            const objs = canvas.getObjects();
            if (objs.length > 0) {
                canvas.setActiveObject(objs[0]);
                canvas.requestRenderAll();
            }
        }""")

        # Simulate Copy
        page.keyboard.press("Control+C")
        page.wait_for_timeout(500)

        # Simulate Paste
        page.keyboard.press("Control+V")
        page.wait_for_timeout(500)

        # Verify objects on canvas
        objects = page.evaluate("""() => {
            return window.canvas.getObjects().map(o => ({ type: o.type, left: o.left, top: o.top, id: o.id }));
        }""")

        assert len(objects) == 2
        assert objects[0]["type"] == "rect"
        assert objects[1]["type"] == "rect"

        # Paste should shift position
        assert objects[1]["left"] != objects[0]["left"]
        assert objects[1]["top"] != objects[0]["top"]

        # IDs must be different
        assert objects[0]["id"] != objects[1]["id"]

        # Now test multiple object selection copy paste
        page.evaluate("""() => {
            const canvas = window.canvas;
            const objs = canvas.getObjects();
            const sel = new fabric.ActiveSelection(objs, { canvas: canvas });
            canvas.setActiveObject(sel);
            canvas.requestRenderAll();
        }""")

        # Simulate Copy
        page.keyboard.press("Control+C")
        page.wait_for_timeout(500)

        # Simulate Paste
        page.keyboard.press("Control+V")
        page.wait_for_timeout(500)

        # Verify objects on canvas
        objects2 = page.evaluate("""() => {
            return window.canvas.getObjects().map(o => ({ type: o.type, left: o.left, top: o.top, id: o.id }));
        }""")

        # Should now have 4 objects total
        assert len(objects2) == 4

        browser.close()
