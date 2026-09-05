import os
import threading
import time
import uuid

import pytest
import uvicorn

os.environ["TESTING"] = "1"

from src.main import app


@pytest.fixture(scope="module")
def test_server():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)
    yield port
    server.should_exit = True
    thread.join(timeout=2)


@pytest.fixture
def svg_file():
    filepath = "test_shape.svg"
    with open(filepath, "w") as f:
        f.write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="red" /></svg>'
        )
    yield filepath
    if os.path.exists(filepath):
        os.remove(filepath)


@pytest.mark.skipif("CI" in os.environ, reason="Playwright tests are skipped in CI")
def test_custom_shape_upload(test_server: int, svg_file: str):
    from playwright.sync_api import sync_playwright

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

        # Set up file chooser for the custom shape input
        with page.expect_file_chooser() as fc_info:
            page.evaluate('document.getElementById("btn-custom-shape").click()')

        file_chooser = fc_info.value
        file_chooser.set_files(svg_file)

        # Wait for the custom shape to be added to the canvas
        page.wait_for_function(
            """
            () => {
                if (!window.canvas) return false;
                const objects = window.canvas.getObjects();
                return objects.some(obj => obj.type === 'group' || obj.type === 'path' || obj.type === 'circle' || obj.type === 'polygon' || obj.type === 'svg');
            }
            """,
            timeout=10000,
        )

        objects = page.evaluate("window.canvas.getObjects().map(obj => obj.type)")
        assert len(objects) >= 1
        browser.close()
