from playwright.sync_api import sync_playwright
import time
import socket
import threading
import uvicorn
import uuid
from src.main import app

def run_server(server):
    server.run()

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("", 0))
port = s.getsockname()[1]
s.close()

config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
server = uvicorn.Server(config)
thread = threading.Thread(target=run_server, args=(server,), daemon=True)
thread.start()
time.sleep(2)

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{port}")

        page.fill("#board-id-input", f"board-{uuid.uuid4().hex[:8]}")
        page.fill("#nickname-input", f"user-{uuid.uuid4().hex[:8]}")
        page.fill("#password-input", "password123")
        page.click("#register-btn")

        page.wait_for_selector("#toolbar", state="visible")

        page.click("#btn-freehand")
        time.sleep(0.5)

        res = page.evaluate("""() => {
            const propStroke = document.getElementById('prop-stroke');
            propStroke.value = '#ff0000';

            // Check if our listeners actually fire and update brush when manually setting value
            if (canvas.isDrawingMode && !window.isEraserMode && !window.isLassoMode) {
                 canvas.freeDrawingBrush.color = propStroke.value;
            }

            return {
                color: canvas.freeDrawingBrush.color,
            };
        }""")
        print("Manual update:", res)

        browser.close()
finally:
    server.should_exit = True
    thread.join()
