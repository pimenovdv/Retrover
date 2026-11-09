import os
import pytest
import uuid
import socket
import uvicorn
import threading
from playwright.sync_api import sync_playwright
import time


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def server_url():
    port = get_free_port()
    from src.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    def run_server():
        server.run()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason='Skipping UI tests in CI')
def test_add_semicircle(server_url):
    board_id = f"test_board_{uuid.uuid4().hex[:8]}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(server_url)

        # Login directly since the TestUser might already be registered in the db from previous tests
        page.fill("#board-id-input", board_id)
        page.fill("#nickname-input", "TestUser")
        page.fill("#password-input", "password123")
        page.click("#login-btn")  # Changing register to login

        try:
            page.wait_for_selector("#btn-semicircle", state="visible", timeout=5000)
        except Exception:
            # Fallback to register if login failed
            page.click("#login-btn")
            try:
                page.wait_for_selector(
                    "#canvas-container", state="visible", timeout=3000
                )
            except Exception:
                page.click("#register-btn")
            page.wait_for_selector("#btn-semicircle", state="visible", timeout=5000)

        page.evaluate("window.canvas !== undefined")

        page.click("#btn-semicircle")

        page.wait_for_function("window.canvas.getObjects().length > 0")

        semicircle_props = page.evaluate("""
            () => {
                const objs = window.canvas.getObjects();
                if (objs.length === 0) return null;
                const doc = objs[0];
                return {
                    type: doc.type,
                    fill: doc.fill,
                    stroke: doc.stroke,
                    path: doc.path
                };
            }
        """)

        assert semicircle_props is not None
        assert semicircle_props["type"] == "path"

        assert len(semicircle_props["path"]) > 0

        assert semicircle_props["fill"].lower().replace(" ", "") in [
            "#ffffff",
            "rgb(255,255,255)",
            "white",
        ]
        assert semicircle_props["stroke"].lower().replace(" ", "") in [
            "#000000",
            "rgb(0,0,0)",
            "black",
        ]

        browser.close()
