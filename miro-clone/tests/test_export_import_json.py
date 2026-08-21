import pytest
import os
import threading
import time
import uuid

import uvicorn
from playwright.sync_api import Page, expect

from src.main import app

@pytest.fixture(scope="module")
def test_server():
    os.environ["TESTING"] = "1"
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1) # Wait for server to start
    yield port
    server.should_exit = True
    thread.join()

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI")
def test_export_import_json(test_server, tmp_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Login
        username = str(uuid.uuid4())
        page.goto(f"http://127.0.0.1:{test_server}/")
        page.fill("#nickname-input", username)
        page.fill("#password-input", "testpass")
        page.click("#register-btn")

        page.wait_for_selector("#canvas-container", state="visible")

        # Add a rectangle
        page.click("#btn-rect")
        page.evaluate("""
            () => new Promise(resolve => {
                const check = () => {
                    if (window.canvas.getObjects().length > 0) {
                        window.canvas.setActiveObject(window.canvas.getObjects()[0]);
                        resolve();
                    } else {
                        setTimeout(check, 100);
                    }
                };
                check();
            })
        """)

        # Lock the rectangle
        page.click("#btn-lock")

        # Ensure it is locked
        locked = page.evaluate("window.canvas.getObjects()[0].locked")
        assert locked

        # Setup download listener
        with page.expect_download() as download_info:
            page.click("#btn-export-json")

        download = download_info.value
        download_path = tmp_path / "board-export.json"
        download.save_as(download_path)

        assert os.path.exists(download_path)

        # Now clear the board
        page.on("dialog", lambda dialog: dialog.accept())
        page.click("#btn-clear-board")

        # Wait for board to clear
        page.evaluate("""
            () => new Promise(resolve => {
                const check = () => {
                    if (window.canvas.getObjects().length === 0) resolve();
                    else setTimeout(check, 100);
                };
                check();
            })
        """)

        assert page.evaluate("window.canvas.getObjects().length") == 0

        # Import the saved JSON
        page.set_input_files("#json-upload-input", download_path)

        # Wait for objects to be imported
        page.evaluate("""
            () => new Promise(resolve => {
                const check = () => {
                    if (window.canvas.getObjects().length > 0) resolve();
                    else setTimeout(check, 100);
                };
                check();
            })
        """)

        objects_count = page.evaluate("window.canvas.getObjects().length")
        assert objects_count == 1

        # Check if the lock state is preserved
        is_locked_after_import = page.evaluate("window.canvas.getObjects()[0].locked")
        assert is_locked_after_import

        browser.close()
