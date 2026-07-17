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
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8002, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time
    time.sleep(1) # wait for server to start

    yield

    server.should_exit = True
    thread.join()

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI due to browser deps")
def test_grid_snapping(app_server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002/")

        # Login
        page.fill("#board-id-input", "grid_snap_board")
        page.fill("#nickname-input", "playwright_user")
        page.click("#join-btn")

        # Wait for canvas
        page.wait_for_selector("#canvas-container", state="visible")

        # Add a rectangle
        page.click("#btn-rect")
        page.wait_for_timeout(1000) # give it time to render and send WS

        # Test dragging without grid snap (should just add delta)
        moved_pos_no_snap = page.evaluate("""() => {
            const canvas = window.canvas;
            const objs = canvas.getObjects();
            if (objs.length === 0) return null;
            const rect = objs[0];

            // Set initial known position
            rect.set({left: 100, top: 100});
            rect.setCoords();

            // Simulate move
            canvas.fire('object:moving', { target: rect });
            rect.set({left: 115, top: 115}); // A random offset not aligned to 20
            canvas.fire('object:moving', { target: rect });

            return { left: rect.left, top: rect.top };
        }""")

        assert moved_pos_no_snap["left"] == 115
        assert moved_pos_no_snap["top"] == 115

        # Enable grid snap
        page.check("#chk-grid-snap")

        # Test dragging with grid snap
        moved_pos_with_snap = page.evaluate("""() => {
            const canvas = window.canvas;
            const objs = canvas.getObjects();
            const rect = objs[0];

            // Simulate move with grid snapping enabled
            rect.set({left: 125, top: 137}); // Some arbitrary offset
            canvas.fire('object:moving', { target: rect });

            return { left: rect.left, top: rect.top };
        }""")

        # 125 / 20 = 6.25 -> 6 * 20 = 120 (math.round(6.25) -> 6)
        # 137 / 20 = 6.85 -> 7 * 20 = 140 (math.round(6.85) -> 7)
        assert moved_pos_with_snap["left"] == 120
        assert moved_pos_with_snap["top"] == 140

        browser.close()
