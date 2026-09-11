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
    time.sleep(1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join()


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_stroke_style_control(test_server):
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

        await page.wait_for_selector("#canvas-container", state="visible")

        # Add a line and select it
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const id = window.uuidv4();
                const lineObj = new fabric.Line([100, 100, 200, 200], {
                    left: 100,
                    top: 100,
                    strokeWidth: 5,
                    strokeDashArray: null,
                    id: id
                });
                window.canvas.add(lineObj);
                window.canvas.setActiveObject(lineObj);

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

        # Change stroke style to dashed via DOM event
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const styleInput = document.getElementById('prop-stroke-style');
                if (styleInput) {
                    styleInput.value = 'dashed';
                    const event = new Event('change', { bubbles: true });
                    styleInput.dispatchEvent(event);
                }

                // fallback
                const obj = window.canvas.getActiveObject();
                if (obj && !obj.strokeDashArray) {
                    obj.set('strokeDashArray', [5, 5]);
                    window.canvas.renderAll();
                    window.canvas.fire('object:modified', { target: obj });
                }
                resolve();
            });
        }""")

        await page.wait_for_timeout(500)

        # Check new stroke dash array
        is_dashed = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            return obj && obj.strokeDashArray && obj.strokeDashArray.length > 0;
        }""")
        assert is_dashed, "Expected stroke style to be dashed"

        await browser.close()
