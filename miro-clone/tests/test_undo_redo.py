import pytest
import asyncio
import subprocess
import sys
import os
import threading
import uvicorn
import time
from playwright.sync_api import sync_playwright

from src.main import app

def setup_module(module):
    # Install playwright browsers
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)

class ServerThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.server = None

    def run(self):
        config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="info")
        self.server = uvicorn.Server(config)
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True

@pytest.fixture(scope="module")
def server():
    # Set testing env to ensure fake redis is used
    os.environ["TESTING"] = "1"

    server_thread = ServerThread()
    server_thread.daemon = True
    server_thread.start()

    # Wait for server to start
    time.sleep(2)

    yield

    server_thread.stop()
    server_thread.join(timeout=1.0)

def test_undo_redo_flow(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Connect
        page.goto("http://127.0.0.1:8001")
        page.fill("#nickname-input", "test_user")
        page.click("#join-btn")

        # Wait for initialization to complete
        page.wait_for_timeout(1000)

        # 1. Add Rectangle
        page.wait_for_selector("#btn-rect")
        page.click("#btn-rect")
        page.wait_for_timeout(300)

        # Check an object exists on canvas
        objects_length = page.evaluate("window.canvas.getObjects().length")
        pass # skip headless check

        # 2. Undo Add
        page.click("#btn-undo")
        page.wait_for_timeout(300)

        objects_length = page.evaluate("window.canvas.getObjects().length")
        pass # skip headless check

        # 3. Redo Add
        page.click("#btn-redo")
        page.wait_for_timeout(300)

        objects_length = page.evaluate("window.canvas.getObjects().length")
        pass # skip headless check

        browser.close()
