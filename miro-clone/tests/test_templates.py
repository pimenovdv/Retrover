import os
import socket
import threading
import time

import pytest
from playwright.sync_api import sync_playwright

os.environ["TESTING"] = "1"

import uvicorn

from src.main import app


@pytest.fixture(scope="module")
def test_server():
    # init_db is not in src.database, we'll just run it. The db is created anyway.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()

    # Wait for server to start
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()


def test_templates_ui(test_server):
    if os.environ.get("CI") == "true":
        pytest.skip("Skipping Playwright tests in CI")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(test_server)

        # Login
        import uuid

        page.fill("#board-id-input", "test_board_" + str(uuid.uuid4()))
        page.fill("#nickname-input", "test_user")
        page.fill("#password-input", "password")
        page.click("#register-btn")

        # Wait for canvas and toolbar to be visible
        page.wait_for_selector("#canvas-container", state="visible")
        page.wait_for_selector("#toolbar", state="visible")

        # Use JS to click the template button to avoid 'element outside of viewport'
        page.evaluate('document.getElementById("btn-templates").click()')

        # Wait for modal
        page.wait_for_selector("#templates-modal", state="visible")

        # Click Flowchart template
        page.click("#btn-template-flowchart")

        # Give it a moment to add objects
        page.wait_for_timeout(500)

        # Check if objects are added to canvas
        objects_count = page.evaluate("canvas.getObjects().length")
        assert objects_count >= 5, "Flowchart template should add at least 5 objects"

        # Check Mind Map
        page.evaluate('document.getElementById("btn-templates").click()')
        page.wait_for_selector("#templates-modal", state="visible")
        page.click("#btn-template-mindmap")

        page.wait_for_timeout(500)

        # Check objects count again (should add at least 7 more)
        new_objects_count = page.evaluate("canvas.getObjects().length")
        assert new_objects_count >= 12, "Mind Map template should add objects"

        browser.close()
