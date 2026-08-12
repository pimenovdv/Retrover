import pytest
import os
os.environ["TESTING"] = "1"
import asyncio
from fastapi.testclient import TestClient
import json

from src.main import app
from src.database import Base, engine

@pytest.fixture(autouse=True, scope="module")
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


def test_ws_coverage():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/new_board/user1") as ws:
            data = ws.receive_json()
            assert data["type"] == "init"

            ws.send_json({
                "action": "add",
                "object": {
                    "id": "obj1",
                    "type": "rect",
                    "left": 0, "top": 0, "width": 100, "height": 100, "fill": "red", "radius": 5, "text": "hello", "fontSize": 12, "z_index": 0
                }
            })

            # test concurrent connection to trigger the board fetch and shape load
            with client.websocket_connect("/ws/new_board/user2") as ws2:
                data2 = ws2.receive_json()
                assert data2["type"] == "init"

                # Should get update
                ws2.send_json({"action": "cursor", "object": {"x": 10, "y": 10}})

                res = ws.receive_json()
                assert res["action"] == "cursor"


@pytest.mark.asyncio
async def test_initialization(setup_db_sync):
    from src.main import db_batcher
    await db_batcher.push("add", {
        "id": "new_sync_obj",
        "type": "rect",
        "left": 0, "top": 0, "width": 100, "height": 100, "fill": "red", "radius": 5, "text": "hello", "fontSize": 12, "z_index": 0,
        "stroke": "black"
    }, board_id="init_board")
    await db_batcher.process_batch()

    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/init_board/user_init") as ws:
            data = ws.receive_json()
            assert data["type"] == "init"
            assert len(data["data"]) == 1
            shape = data["data"][0]
            assert shape["id"] == "new_sync_obj"
            assert shape["type"] == "rect"
            assert shape["width"] == 100
            assert shape["radius"] == 5
            assert shape["text"] == "hello"
            assert shape["fontSize"] == 12
            assert shape["stroke"] == "black"

def test_board_access_control(setup_db_sync):
    client = TestClient(app)
    # Register user1
    client.post("/register", json={"username": "user1", "password": "password"})
    res = client.post("/login", json={"username": "user1", "password": "password"})
    user1_token = res.json()["access_token"]

    # Register a second user
    client.post("/register", json={"username": "user2", "password": "password"})
    res = client.post("/login", json={"username": "user2", "password": "password"})
    user2_token = res.json()["access_token"]

    board_id = "test_board_access"

    # User 1 connects, creates board, becomes owner
    with client.websocket_connect(f"/ws/{board_id}/user1?token={user1_token}") as ws1:
        data = ws1.receive_json()
        assert data["type"] == "init"
        assert data["can_edit"] is True
        assert data["is_owner"] is True

        # User 1 changes access to view
        res = client.put(f"/boards/{board_id}/access", json={"token": user1_token, "public_access": "view"})
        assert res.status_code == 200

        # User 2 tries to change access (should fail)
        res = client.put(f"/boards/{board_id}/access", json={"token": user2_token, "public_access": "edit"})
        assert res.status_code == 403

        # User 2 connects
        with client.websocket_connect(f"/ws/{board_id}/user2?token={user2_token}") as ws2:
            data2 = ws2.receive_json()
            assert data2["type"] == "init"
            assert data2["can_edit"] is False
            assert data2["is_owner"] is False

            # User 2 tries to add a shape
            ws2.send_json({
                "action": "add",
                "object": {"id": "shape1", "type": "rect", "left": 10, "top": 10, "width": 50, "height": 50}
            })

            # Allow some time for processing
            import time
            time.sleep(0.5)

            # Re-connect to check if shape was saved (it shouldn't be)
            with client.websocket_connect(f"/ws/{board_id}/user1?token={user1_token}") as ws1_check:
                data3 = ws1_check.receive_json()
                # Empty board because user2's addition was dropped
                assert len(data3["data"]) == 0
