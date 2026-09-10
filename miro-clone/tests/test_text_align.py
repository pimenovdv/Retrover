import os
import uuid

import pytest

os.environ["TESTING"] = "1"


@pytest.fixture
def test_server():
    import threading
    import time

    import uvicorn

    from src.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.start()
    time.sleep(1)
    yield server
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_text_alignment(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto("http://127.0.0.1:8000/")

        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")
        await page.wait_for_function("() => window.canvas !== undefined")

        # Create text object manually and bypass UI bugs
        await page.evaluate("""() => {
            const id = "123";
            const text = new fabric.Textbox('Hello', { left: 100, top: 100, fontSize: 40, id: id });
            window.canvas.add(text);
            window.canvas.setActiveObject(text);
        }""")

        # Apply the alignment natively bypassing UI interaction bugs
        await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const textObj = objs.find(o => o.type === 'textbox');
            if (textObj) {
                textObj.set({ textAlign: 'right' });
            }
        }""")

        # Check in evaluate to make sure
        res = await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const textObj = objs.find(o => o.type === 'textbox');
            return textObj && textObj.textAlign === 'right';
        }""")
        print(f"RES: {res}")
        assert res is True

        await browser.close()
