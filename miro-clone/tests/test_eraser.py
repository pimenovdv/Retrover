import pytest
import os
import threading
import time

# Set TESTING to use fakeredis and avoid production DB leaks
os.environ["TESTING"] = "1"

@pytest.fixture(scope="module")
def app_server():
    """Runs the FastAPI server in a background thread."""
    from src.main import app
    import uvicorn

    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to start
    time.sleep(1)
    yield "http://127.0.0.1:8001"

    # Cleanup
    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Skipping UI tests in CI")
def test_eraser_tool(app_server):
    from playwright.sync_api import sync_playwright, expect
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to the app
        page.goto(app_server)

        # Login
        page.fill("#board-id-input", "eraser-board")
        page.fill("#nickname-input", "eraser-user")
        page.click("#join-btn")

        # Wait for the canvas to be ready
        page.wait_for_selector("#canvas-container", state="visible")

        # Draw something first
        page.click("#btn-freehand")

        page.mouse.move(200, 200)
        page.mouse.down()
        page.mouse.move(300, 300)
        page.mouse.up()

        # Wait for path creation
        time.sleep(0.5)

        # Check that path was created normally
        time.sleep(1) # Extra wait for enlivenObjects / ws broadcast
        paths_count = page.evaluate("canvas.getObjects().length")
        assert paths_count > 0, f"Expected path, found {paths_count}"

        is_normal_path = page.evaluate("canvas.getObjects()[0].globalCompositeOperation")
        assert is_normal_path == "source-over"

        # Now click eraser
        page.click("#btn-eraser")

        # Verify eraser tool state
        is_eraser_active = page.evaluate("window.isEraserMode === true")
        assert is_eraser_active

        # Verify drawing mode is also active
        is_drawing_mode = page.evaluate("canvas.isDrawingMode")
        assert is_drawing_mode

        # Draw with eraser
        page.mouse.move(250, 250)
        page.mouse.down()
        page.mouse.move(350, 350)
        page.mouse.up()

        time.sleep(0.5)

        time.sleep(1) # Extra wait
        paths_count_new = page.evaluate("canvas.getObjects().length")
        assert paths_count_new > paths_count, f"Expected new path, found {paths_count_new}"

        is_eraser_path = page.evaluate(f"canvas.getObjects()[{paths_count_new - 1}].globalCompositeOperation")
        assert is_eraser_path == "destination-out"

        # Disable eraser
        page.click("#btn-eraser")

        is_eraser_active = page.evaluate("window.isEraserMode === true")
        assert not is_eraser_active

        # Verify drawing mode is off (or back to whatever it was before eraser)
        is_drawing_mode = page.evaluate("canvas.isDrawingMode")
        assert not is_drawing_mode

        browser.close()
