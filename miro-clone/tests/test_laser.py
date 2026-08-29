import os
import pytest
import uuid
import asyncio

os.environ["TESTING"] = "1"

@pytest.mark.skipif(os.environ.get('CI') == 'true', reason="Playwright tests are skipped in CI")
@pytest.mark.asyncio
async def test_laser_pointer():
    from playwright.async_api import async_playwright
    from src.main import app
    import uvicorn
    import threading
    import socket

    # find available port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run)
    server_thread.start()

    await asyncio.sleep(1) # wait for server to start

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # Go to app
            await page.goto(f"http://127.0.0.1:{port}/")

            # Login
            username = str(uuid.uuid4())
            await page.fill('#board-id-input', 'testboard')
            await page.fill('#nickname-input', username)
            await page.fill('#password-input', 'pass123')
            await page.click('#register-btn')

            # Wait for toolbar
            await page.wait_for_selector('#toolbar', state='visible')

            # Verify laser mode is initially false
            is_laser = await page.evaluate('window.isLaserMode')
            assert is_laser is False

            # Click laser button
            await page.evaluate('document.getElementById("btn-laser").click()')
            is_laser = await page.evaluate('window.isLaserMode')
            assert is_laser is True

            # Simulate dragging mouse to draw laser points
            # Wait for canvas to be fully initialized and any existing animations to finish
            await asyncio.sleep(0.5)
            # We don't strictly care about initial circles being exactly 0 as long as new ones are added,
            # but we can filter for our specific is_background circles.
            initial_circles_count = await page.evaluate('canvas.getObjects().filter(o => o.type === "circle" && o.is_background).length')

            # Manually call the window.drawLaserPoint function directly
            # This is simpler and less flaky than simulating complex mouse events
            await page.evaluate('window.drawLaserPoint(150, 150, "red")')

            # We should have a circle
            new_circles_count = await page.evaluate('canvas.getObjects().filter(o => o.type === "circle" && o.is_background).length')
            assert new_circles_count > initial_circles_count

            # Verify they have is_background: true
            has_bg_true = await page.evaluate('canvas.getObjects().filter(o => o.type === "circle" && o.is_background === true).length > 0')
            assert has_bg_true is True

            # Wait a bit to ensure it gets removed
            await asyncio.sleep(1.5)

            # The circle should be removed
            final_circles_count = await page.evaluate('canvas.getObjects().filter(o => o.type === "circle" && o.is_background).length')
            assert final_circles_count == initial_circles_count

            # Click freehand to turn off laser
            await page.evaluate('document.getElementById("btn-freehand").click()')
            is_laser = await page.evaluate('window.isLaserMode')
            assert is_laser is False

            await browser.close()
    finally:
        server.should_exit = True
        server_thread.join()
