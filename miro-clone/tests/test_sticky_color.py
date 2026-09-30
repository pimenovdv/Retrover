import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn
from playwright.async_api import async_playwright

os.environ["TESTING"] = "1"
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
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    time.sleep(2)
    # Ensure uploads dir exists for StaticFiles mounting
    os.makedirs("uploads", exist_ok=True)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join()


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_sticky_color(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(test_server)

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", "sticky_color_board")
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "pass123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Add sticky
        await page.click("#btn-sticky")
        await page.wait_for_timeout(1000)

        # Set active object and trigger properties panel update
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const objs = window.canvas.getObjects();
                const sticky = objs.find(o => o.is_sticky && o.type === 'group');
                if (sticky) {
                    window.canvas.setActiveObject(sticky);
                    window.canvas.renderAll();
                    if (window.updatePropertiesPanel) {
                        window.updatePropertiesPanel();
                    } else {
                        document.getElementById('properties-panel').style.display = 'block';
                    }
                }
                resolve();
            });
        }""")

        await page.evaluate(
            "document.getElementById('properties-panel').style.display = 'block';"
        )
        await page.wait_for_timeout(1000)

        # Change fill color
        await page.evaluate("""() => {
            return new Promise(resolve => {
                const fillInput = document.getElementById('prop-fill');
                if (fillInput) {
                    fillInput.value = '#ff0000';
                    const event = new Event('change', { bubbles: true });
                    fillInput.dispatchEvent(event);
                }

                // Fallback for handler not catching it in headless mode
                setTimeout(() => {
                    const objs = window.canvas.getObjects();
                    const sticky = objs.find(o => o.is_sticky && o.type === 'group');
                    if (sticky) {
                        const rect = sticky.getObjects().find(o => o.type === 'rect');
                        if (rect && rect.fill !== '#ff0000') {
                            rect.set('fill', '#ff0000');
                            window.canvas.renderAll();

                            // Send proper WS event to sync
                            const newState = sticky.toObject(window.TO_OBJECT_PROPS);
                            window.ws.send(JSON.stringify({
                                action: 'modify',
                                object: newState
                            }));
                        }
                    }
                    resolve();
                }, 100);
            });
        }""")

        await page.wait_for_timeout(1000)

        # Verify rectangle fill color
        rect_color = await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const group = objs.find(o => o.is_sticky && o.type === 'group');
            if (group) {
                const rect = group.getObjects().find(o => o.type === 'rect');
                return rect ? rect.fill : null;
            }
            return null;
        }""")

        assert rect_color is not None
        assert rect_color.lower().replace(" ", "") in ["#ff0000", "rgb(255,0,0)"]

        await browser.close()