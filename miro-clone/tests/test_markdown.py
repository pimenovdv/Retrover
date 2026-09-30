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
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()

    time.sleep(2)
    os.makedirs("uploads", exist_ok=True)
    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join()

@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_insert_markdown(test_server):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(test_server)

        # Login
        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#board-id-input", "test-board-markdown")
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "pass123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Wait until window.canvas is available
        await page.wait_for_function("window.canvas !== undefined")

        # Open the Markdown Modal via the Toolbar
        await page.evaluate('document.getElementById("btn-markdown").click()')

        await page.wait_for_selector("#markdown-modal", state="visible")

        # Input markdown text
        markdown_text = "Hello **world**\n*Italics* and ~~strike~~"
        await page.fill("#markdown-input", markdown_text)

        # Click insert
        await page.click('#btn-insert-markdown')

        # Wait for the modal to close and the active object to be set
        await page.wait_for_timeout(500)

        # Check active object in canvas
        active_object_data = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            if (!obj) return null;
            return {
                type: obj.type,
                text: obj.text,
                styles: obj.styles
            };
        }""")

        assert active_object_data is not None, "No active object found after inserting markdown"
        assert active_object_data["type"] == "textbox"
        assert active_object_data["text"] == "Hello world\nItalics and strike"

        # Check styles
        styles = active_object_data["styles"]

        # Line 0: "Hello world"
        # "world" starts at index 6 and ends at 10.
        for i in range(6, 11):
            char_style = styles.get("0", {}).get(str(i), {})
            assert char_style.get("fontWeight") == "bold", f"Char at line 0, index {i} should be bold"

        # Line 1: "Italics and strike"
        # "Italics" starts at index 0 and ends at 6.
        for i in range(0, 7):
            char_style = styles.get("1", {}).get(str(i), {})
            assert char_style.get("fontStyle") == "italic", f"Char at line 1, index {i} should be italic"

        # "strike" starts at index 12 and ends at 17.
        for i in range(12, 18):
            char_style = styles.get("1", {}).get(str(i), {})
            assert char_style.get("linethrough") is True, f"Char at line 1, index {i} should be strikethrough"

        await browser.close()
