import os
import threading
import time
import uuid
import socket

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from src.main import app

os.environ["TESTING"] = "1"

@pytest.fixture(scope="module")
def test_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(2)
    yield port
    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.skipif("CI" in os.environ, reason="Playwright tests are skipped in CI")
def test_forward_backward_z_index(test_server: int):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{test_server}")

        board_id = f"board-{uuid.uuid4().hex[:8]}"
        username = f"user-{uuid.uuid4().hex[:8]}"
        password = "password123"

        page.fill("#board-id-input", board_id)
        page.fill("#nickname-input", username)
        page.fill("#password-input", password)
        page.click("#register-btn")

        page.wait_for_selector("#toolbar", state="visible")

        # Add 3 rectangles
        page.evaluate('document.getElementById("btn-rect").click()')
        time.sleep(1)
        page.evaluate('document.getElementById("btn-rect").click()')
        time.sleep(1)
        page.evaluate('document.getElementById("btn-rect").click()')
        time.sleep(1)

        # Get their UUIDs to identify them
        uuids = page.evaluate("""
            () => {
                return canvas.getObjects().map(obj => obj.id);
            }
        """)
        assert len(uuids) == 3

        obj0 = uuids[0]
        obj1 = uuids[1]
        obj2 = uuids[2]

        # Select the bottom object (obj0)
        page.evaluate(f"""
            () => {{
                const obj = canvas.getObjects().find(o => o.id === "{obj0}");
                canvas.setActiveObject(obj);
                canvas.requestRenderAll();
            }}
        """)
        time.sleep(0.5)

        # Click Bring Forward
        page.evaluate('document.getElementById("btn-bring-forward").click()')
        time.sleep(1)

        # Check new order: obj1, obj0, obj2
        new_uuids = page.evaluate("""
            () => {
                return canvas.getObjects().map(obj => obj.id);
            }
        """)
        assert new_uuids[0] == obj1
        assert new_uuids[1] == obj0
        assert new_uuids[2] == obj2

        # Select the top object (obj2)
        page.evaluate(f"""
            () => {{
                const obj = canvas.getObjects().find(o => o.id === "{obj2}");
                canvas.setActiveObject(obj);
                canvas.requestRenderAll();
            }}
        """)
        time.sleep(0.5)

        # Click Send Backward
        page.evaluate('document.getElementById("btn-send-backward").click()')
        time.sleep(1)

        # Check new order: obj1, obj2, obj0
        new_uuids2 = page.evaluate("""
            () => {
                return canvas.getObjects().map(obj => obj.id);
            }
        """)
        assert new_uuids2[0] == obj1
        assert new_uuids2[1] == obj2
        assert new_uuids2[2] == obj0

        browser.close()
