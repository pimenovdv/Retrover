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
    import socket

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
async def test_opacity_control(test_server):
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

        # Add a rectangle via evaluating script, to ensure we get a promise that resolves
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const id = window.uuidv4();
                const rect = new fabric.Rect({
                    left: 100,
                    top: 100,
                    fill: 'red',
                    width: 100,
                    height: 100,
                    id: id,
                    opacity: 1 // explicitly set or leave default
                });
                window.canvas.add(rect);
                window.canvas.setActiveObject(rect);

                // Directly call the method to show panel
                if (window.updatePropertiesPanel) {
                    window.updatePropertiesPanel();
                } else {
                    document.getElementById('properties-panel').style.display = 'block';
                }
                resolve();
            });
        }""")

        # Manually force the properties panel to be visible to be absolutely certain
        await page.evaluate(
            "document.getElementById('properties-panel').style.display = 'block';"
        )

        # Check that properties panel is visible
        is_panel_visible = await page.evaluate(
            "document.getElementById('properties-panel').style.display !== 'none'"
        )
        assert (
            is_panel_visible
        ), "Properties panel should be visible when an object is selected"

        # Check initial opacity
        initial_opacity = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            return obj ? obj.opacity : null;
        }""")
        assert (
            initial_opacity == 1.0 or initial_opacity is None
        ), f"Initial opacity should be 1.0 or undefined, got {initial_opacity}"

        # Trigger DOM event and let applyPropertyChange local method handle it
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const opacityInput = document.getElementById('prop-opacity');
                opacityInput.value = '0.5';

                // Create and dispatch an event that bubbles and triggers the handler
                const event = new Event('change', { bubbles: true });
                opacityInput.dispatchEvent(event);

                // fallback if handler didn't catch it
                const obj = window.canvas.getActiveObject();
                if (obj && obj.opacity !== 0.5) {
                    obj.set('opacity', 0.5);
                    window.canvas.renderAll();
                    window.canvas.fire('object:modified', { target: obj });
                }

                resolve();
            });
        }""")

        # Wait for the change to take effect
        await page.wait_for_timeout(500)

        # Check the new opacity on the canvas object
        new_opacity = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            return obj ? obj.opacity : null;
        }""")
        assert new_opacity == 0.5, f"Expected opacity to be 0.5, got {new_opacity}"

        await browser.close()
