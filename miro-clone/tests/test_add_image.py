import os
import threading
import time
import uuid

import pytest
import uvicorn

os.environ["TESTING"] = "1"

from src.main import app


@pytest.fixture(scope="module")
def test_server():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)  # Wait for server to start
    yield port
    server.should_exit = True
    thread.join(timeout=2)


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
async def test_add_image(test_server):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"http://127.0.0.1:{test_server}/")

        # Login
        await page.fill("#board-id-input", "image_test_board")
        username = f"user_{uuid.uuid4()}"
        await page.fill("#nickname-input", username)
        await page.fill("#password-input", "password123")
        await page.click("#register-btn")

        await page.wait_for_selector("#canvas-container", state="visible")

        # Wait a bit for WS connection and init
        await page.wait_for_timeout(500)

        # Ensure no images are initially present
        initial_images = await page.evaluate("""() => {
            return window.canvas.getObjects().filter(o => o.type === 'image' && !o.is_background).length;
        }""")
        assert initial_images == 0, "Expected no image objects initially"

        # Create a dummy image file to upload
        dummy_img_path = "tests/dummy_add.png"
        if not os.path.exists("tests"):
            os.makedirs("tests")
        with open(dummy_img_path, "wb") as f:
            # Minimal 1x1 png
            f.write(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        # Intercept file chooser
        async with page.expect_file_chooser() as fc_info:
            # Note: need to bypass CSS 'display: none' timeout in Playwright by direct JS execution or clicking visible trigger
            await page.evaluate('document.getElementById("btn-image").click()')

        file_chooser = await fc_info.value
        await file_chooser.set_files(dummy_img_path)

        # Wait for the image to be processed and added to canvas
        await page.wait_for_timeout(2000)

        # Evaluate canvas state to check for the added image object
        img_objects = await page.evaluate("""() => {
            return window.canvas.getObjects().filter(o => o.type === 'image' && !o.is_background).map(o => ({
                is_background: o.is_background,
                selectable: o.selectable,
                evented: o.evented
            }));
        }""")

        assert (
            len(img_objects) == 1
        ), f"Expected 1 image object, found {len(img_objects)}"
        img = img_objects[0]
        assert img["is_background"] is False
        assert img["selectable"] is True
        assert img["evented"] is True

        await browser.close()

        if os.path.exists(dummy_img_path):
            os.remove(dummy_img_path)
