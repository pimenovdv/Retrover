import os
import threading
import uuid
import time
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    os.environ["TESTING"] = "1"

@pytest.fixture(scope="module")
def app_server():
    from src.main import app
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    os.environ["TEST_PORT"] = str(port)

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)

    yield port

    server.should_exit = True
    thread.join()

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="CI skip")
def test_clustering(app_server):
    port = app_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{port}/")

        page.fill("#board-id-input", "cluster_board")
        username = f"user_{uuid.uuid4()}"
        page.fill("#nickname-input", username)
        page.fill("#password-input", "password123")
        page.click("#register-btn")

        page.wait_for_selector("#canvas-container", state="visible")

        # Add a few stickies
        for _ in range(3):
            page.click("#btn-sticky")
            page.wait_for_timeout(500)

        # Check coordinates before clustering (they should all be at the same default position 300, 300)
        objects_before = page.evaluate("window.canvas.getObjects().map(o => ({id: o.id, left: o.left, top: o.top}))")
        assert len(objects_before) == 3
        for obj in objects_before:
            assert obj["left"] == 300
            assert obj["top"] == 300

        # Click cluster
        page.click("#btn-cluster-stickies")
        page.wait_for_timeout(500)

        # Check coordinates after clustering
        objects_after = page.evaluate("window.canvas.getObjects().map(o => ({id: o.id, left: o.left, top: o.top}))")

        # Assert they are arranged in a grid
        assert objects_after[0]["left"] == 300
        assert objects_after[0]["top"] == 300

        assert objects_after[1]["left"] > 300 # Should be shifted right
        assert objects_after[1]["top"] == 300

        assert objects_after[2]["left"] == 300 # Should be on the next row (since cols = Math.ceil(sqrt(3)) = 2)
        assert objects_after[2]["top"] > 300

        browser.close()
