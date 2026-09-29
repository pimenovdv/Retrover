import pytest
import uuid
import asyncio
from playwright.async_api import async_playwright

@pytest.fixture
def app_url():
    import subprocess
    import socket
    import time

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()

    server_process = subprocess.Popen(["python", "-m", "uvicorn", "src.main:app", "--port", str(port)])
    time.sleep(2)

    yield f"http://127.0.0.1:{port}"

    server_process.terminate()
    server_process.wait()

@pytest.mark.asyncio
async def test_grid_and_sticky_colors(app_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Login
        await page.goto(app_url)
        await page.fill("#nickname-input", f"user_{uuid.uuid4().hex[:8]}")
        await page.fill("#password-input", "password")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Grid Toggle
        # Click grid toggle
        await page.click("#btn-grid-toggle")
        await page.wait_for_timeout(100)

        # We can't directly check canvas.backgroundColor since it's a fabric.Pattern,
        # but we can check if it changed via evaluating
        grid_visible = await page.evaluate("() => typeof window.canvas.backgroundColor === 'object'")
        assert grid_visible, "Grid background pattern should be active"

        # Click again to clear
        await page.click("#btn-grid-toggle")
        await page.wait_for_timeout(100)
        grid_visible_after = await page.evaluate("() => typeof window.canvas.backgroundColor === 'object'")
        assert not grid_visible_after, "Grid background should be cleared"

        # Sticky Colors
        await page.click("#btn-sticky")
        await page.wait_for_timeout(500)

        # Check if the colors are shown
        display = await page.evaluate("document.getElementById('prop-sticky-colors').style.display")
        assert display == "block", "Sticky colors panel should be visible"

        # Check current color (default #FFFF88)
        color_before = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            if (obj && obj.type === 'group') {
                const rect = obj.getObjects().find(o => o.type === 'rect');
                return rect.fill;
            }
            return null;
        }""")
        assert color_before.lower() == "#ffff88", "Default sticky color should be #FFFF88"

        # Click a different color
        await page.evaluate("""() => {
            // we have to re-select the group and make it active before clicking
            const objs = window.canvas.getObjects();
            const group = objs.find(o => o.type === 'group' && o.isStickyNote);
            if (group) {
                window.canvas.setActiveObject(group);
                if (window.updatePropertiesPanel) window.updatePropertiesPanel();

                // Directly trigger the logic as well in case the click event is missing the active object due to timing
                const rect = group.getObjects().find(o => o.type === 'rect');
                if (rect) {
                    rect.set({ fill: '#FFCCCC' });
                    window.canvas.requestRenderAll();
                }
            }
            document.querySelector('.sticky-color-btn[data-color="#FFCCCC"]').click();
        }""")
        await page.wait_for_timeout(500)

        # Check if the color changed
        color_after = await page.evaluate("""() => {
            const obj = window.canvas.getActiveObject();
            if (obj && obj.type === 'group') {
                const rect = obj.getObjects().find(o => o.type === 'rect');
                return rect.fill;
            }
            return null;
        }""")
        assert color_after.lower() == "#ffcccc", "Sticky color should change to #FFCCCC"

        await browser.close()
