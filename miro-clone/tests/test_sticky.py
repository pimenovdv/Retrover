import pytest
import os
import threading
import uvicorn

@pytest.fixture(scope="module", autouse=True)
def setup_test_env():
    os.environ["TESTING"] = "1"

@pytest.fixture(scope="module")
def app_server():
    from src.main import app
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8002, log_level="info")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import time
    time.sleep(1) # wait for server to start

    yield

    server.should_exit = True
    thread.join()

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI due to browser deps")
def test_sticky_note_playwright(app_server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002/")

        # Login
        page.fill("#board-id-input", "sticky_board")
        page.fill("#nickname-input", "playwright_user")
        page.click("#join-btn")

        # Wait for canvas
        page.wait_for_selector("#canvas-container", state="visible")

        # Add a sticky note
        page.click("#btn-sticky")
        page.wait_for_timeout(1000) # give it time to render and send WS

        # Verify objects on canvas
        objects = page.evaluate("""() => {
            return window.canvas.getObjects().map(o => ({ type: o.type, id: o.id }));
        }""")

        assert len(objects) == 1
        assert objects[0]["type"] == "group"

        browser.close()
