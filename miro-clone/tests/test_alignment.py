import os
import threading
import uuid

import pytest
from playwright.sync_api import sync_playwright

os.environ["TESTING"] = "1"

import uvicorn

from src.main import app


@pytest.fixture(scope="module")
def test_server():
    import socket
    import time

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skipping UI tests in CI due to Playwright missing dependencies",
)
def test_alignment(test_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        test_username = f"testuser_{uuid.uuid4().hex}"
        page.goto(f"{test_server}/?board=alignment_board_{uuid.uuid4().hex[:8]}")

        page.wait_for_selector("#login-modal", state="visible")
        page.fill("#nickname-input", test_username)
        page.fill("#password-input", "password123")
        page.click("#register-btn")
        page.wait_for_selector("#login-modal", state="hidden")

        # Add a couple of rectangles
        page.click("#btn-rect")
        page.wait_for_timeout(500)

        page.click("#btn-rect")
        page.wait_for_timeout(500)

        # We need to select them and align them
        page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    const objs = canvas.getObjects();
                    // Just move the second one so they are not perfectly aligned
                    objs[1].set({ left: 300, top: 300 });
                    objs[1].setCoords();
                    canvas.renderAll();

                    const sel = new fabric.ActiveSelection(objs, { canvas: canvas });
                    canvas.setActiveObject(sel);
                    canvas.renderAll();
                    resolve();
                });
            }
        """)

        # Wait a moment for rendering and event handlers
        page.wait_for_timeout(500)

        # Click align center
        page.click("#btn-align-center")
        page.wait_for_timeout(500)

        # Verify alignment
        result = page.evaluate("""
            () => {
                const objs = canvas.getObjects();
                // We aligned center, so their left values should be equal
                // Let's check left property of all non-background objects
                const shapes = objs.filter(o => !o.is_background);
                return shapes.map(o => o.left);
            }
        """)

        assert len(result) >= 2
        # Center alignment aligns them such that they have the same center relative to the group
        # Wait, if we aligned them center in ActiveSelection, their absolute lefts will be the same if they have the same width.
        # But we made sure they are both rects with default width (100). So their lefts should be equal.
        assert (
            result[0] == result[1]
        ), f"Objects were not center aligned. Lefts: {result}"

        browser.close()
