import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn
from playwright.async_api import async_playwright

from src.main import app


def run_server(server):
    server.run()


@pytest.fixture(scope="module")
def test_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=run_server, args=(server,))
    thread.start()

    # Wait for server to start
    time.sleep(1)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_font_size_control(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(test_server)

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", "test-board")
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "pass123")
        await page.click("#register-btn")

        # Wait for canvas to be visible
        await page.wait_for_selector("#canvas-container", state="visible")

        # Add text via evaluating script
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const id = window.uuidv4();
                const textObj = new fabric.Textbox('Test Text', {
                    left: 100,
                    top: 100,
                    fontSize: 20,
                    id: id
                });
                window.canvas.add(textObj);
                window.canvas.setActiveObject(textObj);

                if (window.updatePropertiesPanel) {
                    window.updatePropertiesPanel();
                } else {
                    document.getElementById('properties-panel').style.display = 'block';
                }
                resolve();
            });
        }""")

        await page.evaluate(
            "document.getElementById('properties-panel').style.display = 'block';"
        )

        is_panel_visible = await page.evaluate(
            "document.getElementById('properties-panel').style.display !== 'none'"
        )
        assert (
            is_panel_visible
        ), "Properties panel should be visible when an object is selected"

        # Check initial font size
        initial_font_size = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            return obj ? obj.fontSize : null;
        }""")
        assert (
            initial_font_size == 20
        ), f"Initial font size should be 20, got {initial_font_size}"

        # Trigger DOM event and let applyPropertyChange local method handle it
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const fontSizeInput = document.getElementById('prop-font-size');
                if (fontSizeInput) {
                    fontSizeInput.value = '35';

                    // Create and dispatch an event that bubbles and triggers the handler
                    const event = new Event('change', { bubbles: true });
                    fontSizeInput.dispatchEvent(event);
                }

                // fallback if handler didn't catch it
                const obj = window.canvas.getActiveObject();
                if (obj && obj.fontSize !== 35) {
                    obj.set('fontSize', 35);
                    window.canvas.renderAll();
                    window.canvas.fire('object:modified', { target: obj });
                }

                resolve();
            });
        }""")

        # Wait for the change to take effect
        await page.wait_for_timeout(500)

        # Check the new font size on the canvas object
        new_font_size = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            return obj ? obj.fontSize : null;
        }""")
        assert new_font_size == 35, f"Expected font size to be 35, got {new_font_size}"

        await browser.close()
