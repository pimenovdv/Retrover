import pytest
import os
os.environ["TESTING"] = "1"
import asyncio
from fastapi.testclient import TestClient
import json

from src.main import app
from src.database import Base, engine, AsyncSessionLocal
from src.models import Shape
from sqlalchemy import select

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


def test_shape_rotation_websocket():
    os.environ["TESTING"] = "1"
    with TestClient(app) as client:
        with client.websocket_connect("/ws/rotation_board/user1") as ws:
            # wait for init
            data = ws.receive_json()
            assert data["type"] == "init"

            # Add shape with angle
            ws.send_json({
                "action": "add",
                "object": {
                    "id": "rotated_obj",
                    "type": "rect",
                    "left": 10,
                    "top": 10,
                    "angle": 45
                }
            })

            async def verify_db():
                from src.main import db_batcher
                await asyncio.sleep(0.1)
                await db_batcher.process_batch()
                async with AsyncSessionLocal() as session:
                    result = await session.execute(select(Shape).filter(Shape.id == "rotated_obj"))
                    shape = result.scalars().first()
                    assert shape is not None
                    assert shape.properties is not None
                    assert "angle" in shape.properties
                    assert shape.properties["angle"] == 45

                    # Also test modify
                    await db_batcher.push("modify", {"id": "rotated_obj", "angle": 90}, board_id="rotation_board")
                    await db_batcher.process_batch()

                # Need a new session to see committed changes from process_batch
                async with AsyncSessionLocal() as session:
                    result2 = await session.execute(select(Shape).filter(Shape.id == "rotated_obj"))
                    shape2 = result2.scalars().first()
                    assert shape2.properties["angle"] == 90

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(verify_db())
