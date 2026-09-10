import asyncio
from playwright.async_api import async_playwright
import uuid

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await b.new_page()
        await page.goto("http://127.0.0.1:8000/")
        await page.fill("#nickname-input", f"user_{uuid.uuid4().hex[:8]}")
        await page.fill("#password-input", "password")
        await page.click("#register-btn")
        await page.wait_for_selector("#canvas-container", state="visible")

        await page.click("#btn-text")
        await page.wait_for_timeout(1000)

        await page.evaluate("""() => {
             let objs = window.canvas.getObjects();
             let textObj = objs.find(o => o.type === 'textbox');
             if(textObj) {
                 window.canvas.setActiveObject(textObj);
                 if (window.updatePropertiesPanel) window.updatePropertiesPanel();
             }
        }""")

        # Check immediately
        info = await page.evaluate("""() => {
            const btn = document.getElementById("btn-align-text-right");
            const panel = document.getElementById("properties-panel");
            const prop = document.getElementById("prop-text-align");
            const rect = btn.getBoundingClientRect();
            return {
                panel_display: panel.style.display,
                prop_display: prop.style.display,
                btn_display: window.getComputedStyle(btn).display,
                btn_visibility: window.getComputedStyle(btn).visibility,
                btn_opacity: window.getComputedStyle(btn).opacity,
                rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
                active: !!window.canvas.getActiveObject()
            };
        }""")
        print("VISIBILITY INFO:", info)
        await b.close()

import subprocess, time
server_process = subprocess.Popen(["python", "-m", "uvicorn", "src.main:app", "--port", "8000"])
time.sleep(2)
try:
    asyncio.run(run())
finally:
    server_process.kill()
