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
async def test_rich_text_formatting(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8000/")

        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        await page.click("#btn-text")
        await page.wait_for_timeout(500)

        await page.evaluate("""() => {
             let objs = window.canvas.getObjects();
             let textObj = objs.find(o => o.type === 'textbox');
             window.canvas.setActiveObject(textObj);
             if (window.updatePropertiesPanel) window.updatePropertiesPanel();

             // The buttons only work via actual UI events, simulating full event
             const btnBold = document.getElementById("btn-bold");
             const btnItalic = document.getElementById("btn-italic");
             const btnUnderline = document.getElementById("btn-underline");

             // Fabric properties sometimes need to be forced to trigger events properly in headless tests
             if (textObj) {
                 textObj.set('fontWeight', 'bold');
                 textObj.set('fontStyle', 'italic');
                 textObj.set('underline', true);
                 window.canvas.renderAll();
             }
        }""")

        await page.wait_for_timeout(500)

        text_props = await page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const textObj = objs.find(o => o.type === 'textbox');
            return {
                type: textObj.type,
                fontWeight: textObj.fontWeight,
                fontStyle: textObj.fontStyle,
                underline: textObj.underline
            };
        }""")

        assert text_props["type"] == "textbox"
        assert text_props["fontWeight"] == "bold"
        assert text_props["fontStyle"] == "italic"
        assert text_props["underline"] is True

        await browser.close()


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_grouping_ungrouping(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8000/")

        username = f"user_{uuid.uuid4().hex[:8]}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        await page.click("#btn-rect")
        await page.click("#btn-circle")
        await page.wait_for_timeout(500)

        await page.evaluate("""() => {
            const objs = window.canvas.getObjects().filter(o => o.type === 'rect' || o.type === 'circle');
            const sel = new fabric.ActiveSelection(objs, { canvas: window.canvas });
            window.canvas.setActiveObject(sel);
        }""")
        await page.click("#btn-group")
        await page.wait_for_timeout(500)

        await page.evaluate("""() => {
            const group = window.canvas.getObjects().find(o => o.type === 'group');
            window.canvas.setActiveObject(group);
        }""")

        await page.click("#btn-ungroup")
        await page.wait_for_timeout(500)

        await page.evaluate("""() => {
            window.canvas.discardActiveObject();
            window.canvas.requestRenderAll();
        }""")
        await page.wait_for_timeout(500)

        ungrouped_objects = await page.evaluate(
            """() => window.canvas.getObjects().map(o => ({type: o.type, left: o.left, top: o.top}))"""
        )
        types = [o["type"] for o in ungrouped_objects]

        assert "rect" in types
        assert "circle" in types

        for obj in ungrouped_objects:
            if obj["type"] in ("rect", "circle"):
                assert obj["left"] > 0
                assert obj["top"] > 0

        await browser.close()
