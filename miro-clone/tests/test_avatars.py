import os
import threading
import uuid

import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from src.main import app

# Set testing environment variable
os.environ["TESTING"] = "1"


@pytest.fixture(scope="module")
def server():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)

    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    config.port = port

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time

    time.sleep(1)

    yield port

    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skip UI tests in CI")
def test_avatars(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context1 = browser.new_context()
        page1 = context1.new_page()
        page1.goto(f"http://127.0.0.1:{server}/")

        board_id = f"test-avatar-{uuid.uuid4()}"
        user1 = f"User1_{uuid.uuid4().hex[:6]}"

        page1.fill("#board-id-input", board_id)
        page1.fill("#nickname-input", user1)
        page1.fill("#password-input", "pass123")
        page1.click("#register-btn")

        page1.wait_for_selector("#canvas", state="visible")

        # Simulating the second user sending a cursor event by doing it via page1.evaluate
        # to inject a mock incoming WS message.
        page1.evaluate(f"""
            window.ws.onmessage({{
                data: JSON.stringify({{
                    type: 'update',
                    action: 'cursor',
                    sender: 'User2',
                    board_id: '{board_id}',
                    object: {{x: 100, y: 200}}
                }})
            }});
        """)

        # Wait for the cursor to appear on user1's screen
        cursor_label = page1.wait_for_selector(
            ".remote-cursor-label", state="visible", timeout=5000
        )
        assert cursor_label is not None

        # Check if avatar exists and has correct initials
        avatar = cursor_label.query_selector(".cursor-avatar")
        assert avatar is not None
        assert avatar.inner_text() == "US"  # "US" from "User2"

        # Check text content of the span (username)
        username_span = cursor_label.query_selector("span")
        assert username_span is not None
        assert username_span.inner_text() == "User2"

        browser.close()
