import asyncio
import os
import threading
import uuid
import pytest
from playwright.sync_api import sync_playwright

os.environ["TESTING"] = "1"

import uvicorn
from fastapi.testclient import TestClient

from src.database import Base, engine
from src.main import app

def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8001, log_level="info")
    server = uvicorn.Server(config)
    server.run()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="module")
def test_server():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    loop.close()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    import time
    time.sleep(2)  # wait for server to start
    yield

    loop = asyncio.new_event_loop()
    loop.run_until_complete(drop_db())
    loop.close()

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping UI tests in CI")
def test_duplicate_button_and_shortcut(test_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001")

        board_id = f"test-dup-board-{uuid.uuid4()}"
        username = f"test-dup-user-{uuid.uuid4()}"

        page.fill("#board-id-input", board_id)
        page.fill("#nickname-input", username)
        page.fill("#password-input", "password123")
        page.click("#register-btn")

        page.wait_for_selector("#canvas-container", state="visible")
        page.wait_for_function("() => window.canvas !== undefined")

        # Inject helper to wrap duplicate in a promise
        page.evaluate("""() => {
            // Hook into the original duplicate function by creating a promise that resolves when canvas fires 'object:added'
            window.awaitDuplicate = () => {
                return new Promise(resolve => {
                    const originalCount = window.canvas.getObjects().length;
                    const handler = () => {
                        if (window.canvas.getObjects().length > originalCount) {
                            window.canvas.off('object:added', handler);
                            resolve();
                        }
                    };
                    window.canvas.on('object:added', handler);
                });
            };

            window.duplicateAndAwait = () => {
                return new Promise((resolve) => {
                    const activeObject = window.canvas.getActiveObject();
                    if (!activeObject) { resolve(); return; }

                    activeObject.clone((clonedObj) => {
                        window.canvas.discardActiveObject();
                        clonedObj.set({
                            left: clonedObj.left + 20,
                            top: clonedObj.top + 20,
                            evented: true,
                            id: uuidv4(),
                            z_index: window.getMaxZIndex ? window.getMaxZIndex() + 1 : 999
                        });
                        window.canvas.add(clonedObj);
                        window.canvas.setActiveObject(clonedObj);
                        window.canvas.requestRenderAll();
                        resolve();
                    });
                });
            };
        }""")

        # Add a rectangle manually
        page.evaluate("""() => {
            const rect = new fabric.Rect({
                left: 100,
                top: 100,
                width: 50,
                height: 50,
                fill: 'red',
                id: uuidv4()
            });
            window.canvas.add(rect);
            window.canvas.setActiveObject(rect);
            window.canvas.requestRenderAll();
        }""")

        page.wait_for_function("() => window.canvas.getObjects().length === 1")

        obj_info = page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const obj = objs[0];
            return { id: obj.id, left: obj.left, top: obj.top };
        }""")

        # Duplicate via button
        page.evaluate("() => { window.duplicatePromise = window.awaitDuplicate(); }")
        page.click("#btn-duplicate")
        page.evaluate("async () => { await window.duplicatePromise; }")

        page.wait_for_function("() => window.canvas.getObjects().length === 2")

        dup_info_1 = page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const obj = objs[1];
            return { id: obj.id, left: obj.left, top: obj.top };
        }""")

        assert dup_info_1["id"] != obj_info["id"]
        assert dup_info_1["left"] == obj_info["left"] + 20
        assert dup_info_1["top"] == obj_info["top"] + 20

        # Duplicate via shortcut Ctrl+D
        page.evaluate("() => { window.duplicatePromise = window.awaitDuplicate(); }")
        page.keyboard.press("Control+d")
        page.evaluate("async () => { await window.duplicatePromise; }")

        page.wait_for_function("() => window.canvas.getObjects().length === 3")

        dup_info_2 = page.evaluate("""() => {
            const objs = window.canvas.getObjects();
            const obj = objs[2];
            return { id: obj.id, left: obj.left, top: obj.top };
        }""")

        assert dup_info_2["id"] != dup_info_1["id"]
        assert dup_info_2["left"] == dup_info_1["left"] + 20
        assert dup_info_2["top"] == dup_info_1["top"] + 20

        browser.close()
