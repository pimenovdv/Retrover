import re

with open("miro-clone/tests/test_text_align.py", "r") as f:
    content = f.read()

# Let's fix the test to just force evaluating everything on the browser side.
# I just want to click the button when a text is active.

content = """import os
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

        # Create text object natively via JS because clicking button might cause focus issues in headless
        await page.evaluate('''() => {
            const id = uuidv4();
            const text = new fabric.Textbox('Hello World', {
                left: 300,
                top: 300,
                fontSize: 40,
                fill: 'blue',
                width: 250,
                splitByGrapheme: true,
                id: id
            });
            window.canvas.add(text);
            window.canvas.setActiveObject(text);
            window.updatePropertiesPanel();
        }''')

        # Since updatePropertiesPanel is called, the panel should become visible automatically.
        await page.wait_for_selector("#btn-align-text-right", state="visible", timeout=5000)

        # Click the button natively via Playwright locator (no force)
        await page.locator("#btn-align-text-right").click()

        # Wait for the property to be updated on the active textbox
        await page.wait_for_function('''() => {
            const objs = window.canvas.getObjects();
            const textObj = objs.find(o => o.type === 'textbox');
            return textObj && textObj.textAlign === 'right';
        }''')

        await browser.close()
"""
with open("miro-clone/tests/test_text_align.py", "w") as f:
    f.write(content)
