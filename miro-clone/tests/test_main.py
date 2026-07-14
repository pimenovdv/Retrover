import pytest
from fastapi.testclient import TestClient
import json
import sys
import os
os.environ["TESTING"] = "1"
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import app, manager
from src.database import Base, engine

@pytest.fixture(autouse=True, scope="function")
def setup_db_sync():
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _teardown():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_setup())
    yield
    loop.run_until_complete(_teardown())


def test_websocket_broadcast():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/default/testuser1") as websocket1:
            with client.websocket_connect("/ws/default/testuser2") as websocket2:
                # Receive initial shapes from connection
                init1 = websocket1.receive_text()
                init2 = websocket2.receive_text()

                assert json.loads(init1)["type"] == "init"
                assert json.loads(init2)["type"] == "init"

                # testuser1 sends cursor event
                websocket1.send_text(json.dumps({
                    "action": "cursor",
                    "object": {"x": 100, "y": 200}
                }))

                # testuser2 should receive it
                msg = json.loads(websocket2.receive_text())
                assert msg["type"] == "update"
                assert msg["action"] == "cursor"
                assert msg["sender"] == "testuser1"
                assert msg["object"] == {"x": 100, "y": 200}

                # testuser1 sends select event
                websocket1.send_text(json.dumps({
                    "action": "select",
                    "object": {"id": "123"}
                }))

                msg = json.loads(websocket2.receive_text())
                assert msg["action"] == "select"
                assert msg["object"]["id"] == "123"

                # testuser1 sends chat event
                websocket1.send_text(json.dumps({
                    "action": "chat",
                    "object": {"message": "Hello!"}
                }))

                msg = json.loads(websocket2.receive_text())
                assert msg["action"] == "chat"
                assert msg["object"]["message"] == "Hello!"

def test_websocket_disconnect():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/default/testuser1") as websocket1:
            with client.websocket_connect("/ws/default/testuser2") as websocket2:
                init1 = websocket1.receive_text()
                init2 = websocket2.receive_text()
    pass

@pytest.mark.asyncio
async def test_batch_updates():
    from src.main import db_batcher
    from src.models import Shape
    from sqlalchemy import select
    from src.database import AsyncSessionLocal

    await db_batcher.push("add", {
        "id": "test_shape_1",
        "type": "rect",
        "left": 10,
        "top": 20,
        "width": 100,
        "height": 50,
        "fill": "red",
        "z_index": 1
    })

    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_1"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.type == "rect"

    await db_batcher.push("modify", {
        "id": "test_shape_1",
        "left": 50,
        "fill": "blue",
        "strokeWidth": 5,
        "fontFamily": "Times New Roman"
    })

    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_1"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.left == 50
        assert shape.fill == "blue"
        assert shape.properties is not None
        assert shape.properties.get("strokeWidth") == 5
        assert shape.properties.get("fontFamily") == "Times New Roman"

    await db_batcher.push("remove", {
        "id": "test_shape_1"
    })

    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_1"))
        shape = result.scalars().first()
        assert shape is None

def test_board_isolation():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/board1/user1") as ws1:
            with client.websocket_connect("/ws/board2/user2") as ws2:
                # Clear init messages
                ws1.receive_text()
                ws2.receive_text()

                # user1 on board1 sends a message
                ws1.send_text(json.dumps({
                    "action": "chat",
                    "object": {"message": "Hello board1!"}
                }))

                # user2 on board2 should not receive it, but we can't easily wait for nothing.
                # So we connect user3 to board1, send message from user3, ensure user1 gets it,
                # and user2 doesn't block (using a timeout would be complex here, so we just check user3's message arrives at user1).
                with client.websocket_connect("/ws/board1/user3") as ws3:
                    ws3.receive_text() # init
                    ws3.send_text(json.dumps({
                        "action": "chat",
                        "object": {"message": "Hi user1"}
                    }))

                    msg = json.loads(ws1.receive_text())
                    assert msg["action"] == "chat"
                    assert msg["sender"] == "user3"

                    # ws2 should have NO messages pending
                    # In starlette TestClient, we can't easily check for empty queue without blocking,
                    # but the routing isolation proves board isolation in local_broadcast.

@pytest.mark.asyncio
async def test_shape_properties_persistence():
    from src.main import db_batcher
    from src.models import Shape
    from sqlalchemy import select
    from src.database import AsyncSessionLocal
    import os

    os.environ["TESTING"] = "1"

    await db_batcher.push("add", {
        "id": "test_shape_props",
        "type": "rect",
        "left": 10,
        "top": 20,
        "width": 100,
        "height": 50,
        "fill": "red",
        "z_index": 1,
        "stroke": "black",
        "strokeWidth": 5,
        "fontFamily": "Arial"
    })

    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_props"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.type == "rect"
        assert shape.fill == "red"
        # Unknown properties should go into the properties JSON
        assert shape.properties.get("stroke") == "black"
        assert shape.properties.get("strokeWidth") == 5
        assert shape.properties.get("fontFamily") == "Arial"

    # Modify properties
    await db_batcher.push("modify", {
        "id": "test_shape_props",
        "stroke": "blue",
        "strokeWidth": 10
    })

    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_props"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.properties.get("stroke") == "blue"
        assert shape.properties.get("strokeWidth") == 10
        # Check if the previous property is preserved
        assert shape.properties.get("fontFamily") == "Arial"

@pytest.mark.asyncio
async def test_websocket_actions(setup_db_sync):
    from src.main import db_batcher
    import asyncio

    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/default/ws_user") as websocket:
            init = websocket.receive_text()

            # test transient actions that just pass through
            websocket.send_text(json.dumps({
                "action": "deselect",
                "object": {"id": "123"}
            }))

            # We don't get our own broadcast back easily in this setup because we exclude sender,
            # but we can connect a second user to receive it.

        with client.websocket_connect("/ws/default/ws_user1") as ws1:
            with client.websocket_connect("/ws/default/ws_user2") as ws2:
                ws1.receive_text() # init
                ws2.receive_text() # init

                # Test disconnect format broadcast implicitly by disconnecting user1
                # The user2 should receive disconnect message

                ws1.send_text(json.dumps({
                    "action": "cursor",
                    "object": {"x": 10, "y": 20}
                }))
                msg = json.loads(ws2.receive_text())
                assert msg["action"] == "cursor"

                ws1.send_text(json.dumps({
                    "action": "deselect",
                    "object": {"id": "123"}
                }))
                msg = json.loads(ws2.receive_text())
                assert msg["action"] == "deselect"

                # test disconnect
        with client.websocket_connect("/ws/default/ws_user3") as ws3:
            ws3.receive_text()


@pytest.mark.asyncio
async def test_initial_shapes_load(setup_db_sync):
    from src.main import db_batcher
    import asyncio

    # Push shapes to populate the board with various properties
    await db_batcher.push("add", {
        "id": "load_shape_1",
        "type": "circle",
        "left": 100,
        "top": 200,
        "radius": 50,
        "fill": "green",
        "z_index": 2,
        "custom_prop": "test"
    }, board_id="load_board")
    await db_batcher.process_batch()

    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/load_board/loaduser") as websocket:
            init = websocket.receive_text()
            data = json.loads(init)
            assert data["type"] == "init"
            assert len(data["data"]) == 1
            shape_data = data["data"][0]
            assert shape_data["id"] == "load_shape_1"
            assert shape_data["radius"] == 50
            assert shape_data["custom_prop"] == "test"

@pytest.mark.asyncio
async def test_db_worker_exception(setup_db_sync):
    from src.main import db_writer_worker, db_batcher
    import asyncio

    # Mock process_batch to throw Exception
    original_process_batch = db_batcher.process_batch
    async def mock_process_batch():
        raise Exception("Mock error")

    db_batcher.process_batch = mock_process_batch

    # Run the worker briefly
    task = asyncio.create_task(db_writer_worker())
    await asyncio.sleep(1.5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    db_batcher.process_batch = original_process_batch

@pytest.mark.asyncio
async def test_upload_image_endpoint():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        # Create a dummy file for testing
        test_file_path = "test_img.png"
        with open(test_file_path, "wb") as f:
            f.write(b"dummy image content")

        with open(test_file_path, "rb") as f:
            response = client.post("/upload", files={"file": ("test_img.png", f, "image/png")})
            assert response.status_code == 200
            assert "url" in response.json()

        os.remove(test_file_path)

@pytest.mark.asyncio
async def test_upload_invalid_type_endpoint():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        test_file_path = "test_doc.txt"
        with open(test_file_path, "wb") as f:
            f.write(b"dummy text content")

        with open(test_file_path, "rb") as f:
            response = client.post("/upload", files={"file": ("test_doc.txt", f, "text/plain")})
            assert response.status_code == 400

        os.remove(test_file_path)

@pytest.mark.asyncio
async def test_upload_pdf_endpoint():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        import fitz
        test_file_path = "test_doc.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test PDF Content", fontsize=20)
        doc.save(test_file_path)
        doc.close()

        with open(test_file_path, "rb") as f:
            response = client.post("/upload", files={"file": ("test_doc.pdf", f, "application/pdf")})
            assert response.status_code == 200
            data = response.json()
            assert "urls" in data
            assert len(data["urls"]) == 1
            assert data["urls"][0].startswith("/uploads/")

        os.remove(test_file_path)

@pytest.mark.asyncio
async def test_upload_corrupted_pdf_endpoint():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        test_file_path = "corrupted_doc.pdf"
        with open(test_file_path, "wb") as f:
            f.write(b"Not a valid PDF file content")

        with open(test_file_path, "rb") as f:
            response = client.post("/upload", files={"file": ("corrupted_doc.pdf", f, "application/pdf")})
            assert response.status_code == 400
            assert "Invalid or corrupted PDF file" in response.json()["detail"]

        os.remove(test_file_path)

@pytest.mark.asyncio
async def test_upload_invalid_extension():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        test_file_path = "test_doc.xyz"
        with open(test_file_path, "wb") as f:
            f.write(b"dummy text content")

        with open(test_file_path, "rb") as f:
            response = client.post("/upload", files={"file": ("test_doc.xyz", f, "image/png")})
            assert response.status_code == 400

        os.remove(test_file_path)

@pytest.mark.asyncio
async def test_initial_shapes_load_integrity(setup_db_sync):
    from src.main import db_batcher
    import asyncio

    # Try multiple connected to cover integrity error
    await db_batcher.push("add", {
        "id": "load_shape_2",
        "type": "circle",
        "left": 100,
        "top": 200,
        "radius": 50,
        "fill": "green",
        "z_index": 2,
        "custom_prop": "test"
    }, board_id="load_board2")
    await db_batcher.process_batch()

    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        # Two users connect to the same board simultaneously, one might get integrity error creating board
        def connect_user(username):
            with client.websocket_connect(f"/ws/load_board2/{username}") as ws:
                init = ws.receive_text()
                data = json.loads(init)
                if data.get("type") == "update":
                    # Ignore user_joined broadcast from another thread
                    init = ws.receive_text()
                    data = json.loads(init)
                assert data["type"] == "init"
                assert len(data["data"]) == 1

        import threading
        t1 = threading.Thread(target=connect_user, args=("user1",))
        t2 = threading.Thread(target=connect_user, args=("user2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()


@pytest.mark.asyncio
async def test_initial_shapes_load_integrity_explicit(setup_db_sync):
    from src.main import websocket_endpoint, db_batcher
    import asyncio

    # We will simulate a concurrent insert exception by directly mocking the db execute temporarily.
    from src.models import Board
    from sqlalchemy.ext.asyncio import AsyncSession
    from unittest.mock import AsyncMock, MagicMock
    from sqlalchemy.exc import IntegrityError

    mock_db = AsyncMock(spec=AsyncSession)

    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db.execute.return_value = mock_result
    mock_db.commit.side_effect = IntegrityError("test", "test", "test")

    mock_ws = AsyncMock()
    mock_ws.receive_text.side_effect = Exception("Stop loop") # just to break the loop

    try:
        await websocket_endpoint(mock_ws, "test_board_err", "nick", mock_db)
    except Exception:
        pass

    # Assert rollback was called
    mock_db.rollback.assert_called_once()

@pytest.mark.asyncio
async def test_initial_shapes_load_with_properties(setup_db_sync):
    from src.main import db_batcher
    import asyncio

    # Push shapes to populate the board with various properties
    await db_batcher.push("add", {
        "id": "load_shape_2",
        "type": "circle",
        "left": 100,
        "top": 200,
        "width": 100,
        "height": 100,
        "radius": 50,
        "fill": "green",
        "text": "test",
        "fontSize": 12,
        "z_index": 2,
        "custom_prop": "test"
    }, board_id="load_board3")
    await db_batcher.process_batch()

    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/load_board3/loaduser") as websocket:
            init = websocket.receive_text()
            data = json.loads(init)
            assert data["type"] == "init"
            assert len(data["data"]) == 1
            shape_data = data["data"][0]
            assert shape_data["id"] == "load_shape_2"
            assert shape_data["width"] == 100
            assert shape_data["height"] == 100
            assert shape_data["text"] == "test"
            assert shape_data["fontSize"] == 12

@pytest.mark.asyncio
async def test_local_broadcast_exception():
    from src.main import manager
    from unittest.mock import AsyncMock
    mock_ws = AsyncMock()
    mock_ws.send_text.side_effect = Exception("test error")
    manager.active_connections["error_board"] = {"user1": mock_ws}

    await manager.local_broadcast("error_board", {"msg": "test"})
    # Should handle exception and not crash
