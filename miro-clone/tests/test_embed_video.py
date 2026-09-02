import os
import threading
import uuid
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

os.environ["TESTING"] = "1"
from src.main import app

@pytest.fixture(scope="module")
def server():
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)

    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    server.config.port = port

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time
    time.sleep(1) # wait for server to start

    yield port

    server.should_exit = True
    thread.join(timeout=2)

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skip UI tests in CI")
def test_embed_video(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(f"http://127.0.0.1:{server}")

        # Login
        test_user = f"user_{uuid.uuid4().hex[:8]}"
        page.fill("#nickname-input", test_user)
        page.fill("#password-input", "testpass")
        page.fill("#board-id-input", f"board_{uuid.uuid4().hex[:8]}")
        page.click("#register-btn")

        page.wait_for_selector("#canvas-container", state="visible")

        # Override prompt to simulate entering a URL
        page.evaluate("window.prompt = () => 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';")

        # Click Embed Video
        page.click("#btn-embed")

        # Verify an iframe was added
        page.wait_for_selector("#iframe-container iframe", state="visible")

        iframe_src = page.eval_on_selector("#iframe-container iframe", "el => el.src")
        assert "youtube.com/embed/dQw4w9WgXcQ" in iframe_src

        browser.close()
