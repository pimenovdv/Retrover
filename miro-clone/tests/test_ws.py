import pytest
import os
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
