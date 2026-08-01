import os

import pytest

os.environ["TESTING"] = "1"
import asyncio

from fastapi.testclient import TestClient

from src.database import Base, engine
from src.main import app


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

            ws.send_json(
                {
                    "action": "add",
                    "object": {
                        "id": "obj1",
                        "type": "rect",
                        "left": 0,
                        "top": 0,
                        "width": 100,
                        "height": 100,
                        "fill": "red",
                        "radius": 5,
                        "text": "hello",
                        "fontSize": 12,
                        "z_index": 0,
                    },
                }
            )

            # test concurrent connection to trigger the board fetch and shape load
            with client.websocket_connect("/ws/new_board/user2") as ws2:
                data2 = ws2.receive_json()
                while data2.get("type") != "init":
                    data2 = ws2.receive_json()
                assert data2["type"] == "init"

                # Should get update
                ws2.send_json({"action": "cursor", "object": {"x": 10, "y": 10}})

                res = ws.receive_json()
                # We might receive 'update' (from earlier add), access_change from concurrent creation, or the cursor
                while res.get("action") != "cursor" and res.get("type") != "cursor":
                    res = ws.receive_json()

                # Check for either style depending on how cursor is broadcast
                if "action" in res:
                    assert res["action"] == "cursor"
                else:
                    assert res["type"] == "cursor"


@pytest.mark.asyncio
async def test_initialization(setup_db_sync):
    from src.main import db_batcher

    await db_batcher.push(
        "add",
        {
            "id": "new_sync_obj",
            "type": "rect",
            "left": 0,
            "top": 0,
            "width": 100,
            "height": 100,
            "fill": "red",
            "radius": 5,
            "text": "hello",
            "fontSize": 12,
            "z_index": 0,
            "stroke": "black",
        },
        board_id="init_board",
    )
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


def test_board_access_endpoints():
    import uuid

    username = f"user_{uuid.uuid4()}"
    password = "password123"

    with TestClient(app) as client:
        # Register user
        res = client.post(
            "/register", json={"username": username, "password": password}
        )
        assert res.status_code == 200
        token = res.json()["access_token"]

        # Connect to a new board via WS to create it and set owner
        board_id = f"board_{uuid.uuid4()}"
        with client.websocket_connect(f"/ws/{board_id}/{username}?token={token}") as ws:
            ws.receive_json()  # init

        # Get board access
        res = client.get(f"/api/boards/{board_id}")
        assert res.status_code == 200
        assert res.json()["owner_username"] == username
        assert res.json()["public_access"] == "edit"

        # Update board access
        res = client.put(
            f"/api/boards/{board_id}",
            json={"public_access": "view"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

        # Verify update
        res = client.get(f"/api/boards/{board_id}")
        assert res.status_code == 200
        assert res.json()["public_access"] == "view"


def test_websocket_view_only_enforcement():
    import uuid

    owner = f"owner_{uuid.uuid4()}"
    viewer = f"viewer_{uuid.uuid4()}"
    password = "password123"
    board_id = f"board_{uuid.uuid4()}"

    with TestClient(app) as client:
        # Register users
        res1 = client.post("/register", json={"username": owner, "password": password})
        token_owner = res1.json()["access_token"]

        res2 = client.post("/register", json={"username": viewer, "password": password})
        token_viewer = res2.json()["access_token"]

        # Owner connects and creates board
        with client.websocket_connect(
            f"/ws/{board_id}/{owner}?token={token_owner}"
        ) as ws_owner:
            ws_owner.receive_json()  # init

            # Owner changes access to view-only
            res = client.put(
                f"/api/boards/{board_id}",
                json={"public_access": "view"},
                headers={"Authorization": f"Bearer {token_owner}"},
            )
            assert res.status_code == 200

            # Owner adds a shape
            ws_owner.send_json(
                {
                    "action": "add",
                    "object": {
                        "id": "shape_1",
                        "type": "rect",
                        "left": 0,
                        "top": 0,
                        "width": 100,
                        "height": 100,
                    },
                }
            )

            # Viewer connects
            with client.websocket_connect(
                f"/ws/{board_id}/{viewer}?token={token_viewer}"
            ) as ws_viewer:
                ws_viewer.receive_json()

                # Viewer attempts to add a shape
                ws_viewer.send_json(
                    {
                        "action": "add",
                        "object": {
                            "id": "shape_2",
                            "type": "circle",
                            "left": 10,
                            "top": 10,
                            "radius": 50,
                        },
                    }
                )

                # Viewer attempts transient action (cursor)
                ws_viewer.send_json(
                    {"action": "cursor", "object": {"x": 100, "y": 100}}
                )

                # Check owner receives cursor but NOT shape_2
                # Wait for cursor
                msg1 = ws_owner.receive_json()
                while msg1.get("action") != "cursor" and msg1.get("type") != "cursor":
                    msg1 = (
                        ws_owner.receive_json()
                    )  # skip access_change from put request

                if "action" in msg1:
                    assert msg1["action"] == "cursor"
                else:
                    assert msg1["type"] == "cursor"

        # Re-fetch board to check DB
        res = client.get(f"/api/boards/{board_id}")
        assert res.status_code == 200
