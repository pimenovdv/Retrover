import pytest
from fastapi.testclient import TestClient
from src.main import app
import os
import tempfile
import shutil

@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup: ensure testing env var is set
    os.environ["TESTING"] = "1"

    # Store original directories
    original_cwd = os.getcwd()
    temp_dir = tempfile.mkdtemp()

    # Create static/index.html in temp dir
    os.makedirs(os.path.join(temp_dir, "static"), exist_ok=True)
    with open(os.path.join(temp_dir, "static", "index.html"), "w") as f:
        f.write("<html><body>Test</body></html>")

    # Create uploads dir
    os.makedirs(os.path.join(temp_dir, "uploads"), exist_ok=True)

    # Change working directory for FileResponse and uploads to work with temp
    os.chdir(temp_dir)

    yield

    # Teardown
    os.chdir(original_cwd)
    shutil.rmtree(temp_dir)

def test_get_root():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200

def test_websocket_actions():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/board1/user1") as ws:
            msg = ws.receive_text()
            assert "init" in msg

            ws.send_json({
                "action": "add",
                "object": {"id": "shape_2", "type": "circle", "left": 10, "top": 20, "radius": 15, "fill": "blue"}
            })
            ws.send_json({
                "action": "modify",
                "object": {"id": "shape_2", "left": 15}
            })
            ws.send_json({
                "action": "remove",
                "object": {"id": "shape_2"}
            })

def test_upload_image():
    with TestClient(app) as client:
        files = {"file": ("test_image.png", b"fake_image_content", "image/png")}
        response = client.post("/upload", files=files)
        assert response.status_code == 200
        assert "url" in response.json()

@pytest.mark.asyncio
async def test_websocket_db_load():
    from src.models import Shape, Board
    from sqlalchemy import select
    from src.database import AsyncSessionLocal
    from src.main import db_batcher

    await db_batcher.push("add", {
        "id": "shape_100",
        "type": "rect",
        "left": 10,
        "top": 20,
        "width": 100,
        "height": 50,
        "fill": "red",
        "z_index": 1,
        "radius": 5,
        "text": "hello",
        "fontSize": 12,
        "stroke": "black",
        "strokeWidth": 5,
        "fontFamily": "Arial",
        "board_id": "test_board_load"
    }, board_id="test_board_load")

    await db_batcher.process_batch()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/test_board_load/user_load") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "init"
            assert len(msg["data"]) > 0

            ws.send_json({
                "action": "move_batch",
                "objects": [{"id": "shape_100", "left": 100, "top": 200}]
            })

            ws.send_json({
                "action": "z_index_batch",
                "objects": [{"id": "shape_100", "z_index": 5}]
            })

@pytest.mark.asyncio
async def test_db_batcher_logic():
    from src.main import db_batcher

    await db_batcher.push("add", {"some": "data"})
    await db_batcher.push("add", {"id": "obj1", "val": 1})
    await db_batcher.push("modify", {"id": "obj1", "val": 2})
    await db_batcher.push("modify", {"id": "obj2", "val": 1})
    await db_batcher.push("modify", {"id": "obj2", "val": 2})
    await db_batcher.push("remove", {"id": "obj3"})
    await db_batcher.push("add", {"id": "obj3", "val": 1})
    await db_batcher.push("add", {"id": "obj4"})
    await db_batcher.push("remove", {"id": "obj4"})

    await db_batcher.process_batch()

def test_websocket_broadcast_exception():
    from unittest.mock import AsyncMock
    from src.main import manager
    import asyncio

    class BadConnection:
        async def send_text(self, text):
            raise Exception("Test exception")

    manager.active_connections["board_bad"] = {"user_bad": BadConnection()}
    asyncio.run(manager.local_broadcast("board_bad", {"msg": "hi"}))

@pytest.mark.asyncio
async def test_db_writer_worker():
    from src.main import db_writer_worker
    import asyncio

    task = asyncio.create_task(db_writer_worker())
    await asyncio.sleep(1.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

@pytest.mark.asyncio
async def test_websocket_endpoint_existing_board():
    from src.models import Shape, Board
    from sqlalchemy import select
    from src.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        b = Board(id="pre_board", name="Pre Board")
        session.add(b)
        s = Shape(
            id="s1", board_id="pre_board", type="circle",
            left=10, top=10, z_index=1,
            width=20, height=20, fill="blue", radius=10, text="hi", fontSize=14,
            properties={"extra": "prop"}
        )
        session.add(s)
        await session.commit()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/pre_board/pre_user") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "init"

def test_websocket_exceptions():
    from fastapi import WebSocketDisconnect

    class MockWS:
        async def send_text(self, data): pass
        async def receive_text(self):
            raise WebSocketDisconnect()

    with TestClient(app) as client:
        with client.websocket_connect("/ws/disconnect_board/disc_user") as ws:
            pass

@pytest.mark.asyncio
async def test_db_batcher_merge_other():
    from src.main import db_batcher
    db_batcher.queue.clear()
    await db_batcher.push("modify", {"id": "x1", "val": 1})
    await db_batcher.push("remove", {"id": "x1"})
    await db_batcher.push("remove", {"id": "x2"})
    await db_batcher.push("remove", {"id": "x2"})
    await db_batcher.process_batch()

def test_upload_image_invalid():
    with TestClient(app) as client:
        files = {"file": ("test.txt", b"text", "text/plain")}
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400

        files = {"file": ("test.txt", b"image", "image/png")}
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400

def test_upload_pdf():
    with TestClient(app) as client:
        import fitz

        # the setup_teardown fixture changed os.getcwd() to the temp_dir
        pdf_path = "test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test", fontsize=20)
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2", fontsize=20)
        doc.save(pdf_path)
        doc.close()

        with open(pdf_path, "rb") as f:
            files = {"file": ("test.pdf", f, "application/pdf")}
            response = client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "urls" in data
        assert len(data["urls"]) == 2
        for url in data["urls"]:
            assert url.startswith("/uploads/")
            assert url.endswith(".png")

def test_upload_pdf_invalid():
    with TestClient(app) as client:
        files = {"file": ("test.pdf", b"This is not a real PDF file", "application/pdf")}
        resp = client.post("/upload", files=files)
        assert resp.status_code == 400
        assert "Invalid or corrupted PDF file" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_db_batcher_add_add():
    from src.main import db_batcher
    db_batcher.queue.clear()

    await db_batcher.push("add", {"id": "x3"})
    await db_batcher.push("add", {"id": "x3", "val": 2})

    db_batcher.queue.clear()
    original_process = db_batcher.process_batch

    async def bad_batch():
        raise Exception("test")
    db_batcher.process_batch = bad_batch

    from src.main import db_writer_worker
    import asyncio
    task = asyncio.create_task(db_writer_worker())
    await asyncio.sleep(1.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    db_batcher.process_batch = original_process
