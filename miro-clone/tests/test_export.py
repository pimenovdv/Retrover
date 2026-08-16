import uuid
import os
import pytest
import uvicorn
import threading

os.environ["TESTING"] = "1"

from src.main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8006, log_level="error")

@pytest.fixture(scope="module")
def server():
    # Start server in a separate thread
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    import time
    time.sleep(1) # wait for server to start
    yield
    # No explicit shutdown needed as it's a daemon thread

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI")
def test_export_image(server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate and join the board
        page.goto("http://127.0.0.1:8006")
        page.fill("#board-id-input", "export-test-board")
        username = f"user_{uuid.uuid4()}"
        page.fill("#nickname-input", username)
        page.fill("#password-input", "password123")
        page.click("#register-btn")

        # Wait for the toolbar and canvas to appear
        page.wait_for_selector("#toolbar", state="visible")
        page.wait_for_selector("#canvas-container", state="visible")

        # Add a rectangle so the canvas isn't empty
        page.click("#btn-rect")
        page.wait_for_timeout(500)

        # Click export and intercept the download
        with page.expect_download() as download_info:
            page.click("#btn-export")
        download = download_info.value

        # Check download properties
        assert download.suggested_filename == "board-export-test-board-export.png"

        # Save and verify the file size
        download_path = "/tmp/export_test.png"
        download.save_as(download_path)
        assert os.path.exists(download_path)
        assert os.path.getsize(download_path) > 0

        # Cleanup
        os.remove(download_path)

        # Test Export PDF
        with page.expect_download() as download_info_pdf:
            page.click("#btn-export-pdf")
        download_pdf = download_info_pdf.value

        assert download_pdf.suggested_filename == "board-export-test-board-export.pdf"

        download_path_pdf = "/tmp/export_test.pdf"
        download_pdf.save_as(download_path_pdf)
        assert os.path.exists(download_path_pdf)
        assert os.path.getsize(download_path_pdf) > 0

        os.remove(download_path_pdf)

        browser.close()
