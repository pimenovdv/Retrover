import os
import threading
import time
import uuid

import pytest
import uvicorn

from src.main import app


@pytest.fixture(scope="module")
def test_server():
    os.environ["TESTING"] = "1"
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)  # Wait for server to start
    yield port
    server.should_exit = True
    thread.join()


@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
def test_lock_unlock(test_server):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        username = str(uuid.uuid4())
        page.goto(f"http://127.0.0.1:{test_server}/")
        page.fill("#nickname-input", username)
        page.fill("#password-input", "testpass")
        page.click("#register-btn")

        page.wait_for_selector("#canvas-container", state="visible")

        # Add a rectangle
        page.click("#btn-rect")

        # Wait for rect to be added and selected
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

        # Check it's initially not locked
        locked = page.evaluate("window.canvas.getActiveObject()?.locked")
        assert not locked

        # Ensure object is active and click lock button
        page.evaluate("""
            const obj = window.canvas.getObjects()[0];
            window.canvas.setActiveObject(obj);
            if (window.updatePropertiesPanel) window.updatePropertiesPanel();
            window.canvas.requestRenderAll();
        """)

        # Click the lock button directly via evaluate to avoid playwright "element outside of viewport" errors
        # if the toolbar is too wide.
        page.evaluate("""
            const lockBtn = document.getElementById("btn-lock");
            if (lockBtn) lockBtn.click();
        """)
        page.wait_for_timeout(1000)

        locked = page.evaluate("window.canvas.getObjects()[0].locked")
        assert locked

        has_controls = page.evaluate("window.canvas.getObjects()[0].hasControls")
        assert not has_controls

        # Unlock it
        page.evaluate("""
            const obj = window.canvas.getObjects()[0];
            window.canvas.setActiveObject(obj);
            if (window.updatePropertiesPanel) window.updatePropertiesPanel();
            window.canvas.requestRenderAll();
        """)
        page.evaluate("""
            const lockBtn = document.getElementById("btn-lock");
            if (lockBtn) lockBtn.click();
        """)
        page.wait_for_timeout(1000)

        locked = page.evaluate("window.canvas.getObjects()[0].locked")
        assert not locked

        has_controls = page.evaluate("window.canvas.getObjects()[0].hasControls")
        assert has_controls
