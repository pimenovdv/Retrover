import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import db_batcher
from src.models import Shape
from sqlalchemy import select
from src.database import AsyncSessionLocal, Base, engine
import asyncio
import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_db_sync():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_batch_updates(setup_db_sync):
    # Push add
    await db_batcher.push("add", { "board_id": "default",
        "id": "test_shape_1",
        "type": "rect",
        "left": 10,
        "top": 20,
        "width": 100,
        "height": 50,
        "fill": "red",
        "z_index": 1
    })

    # Process batch
    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_1"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.type == "rect"
        assert shape.left == 10
        assert shape.top == 20
        assert shape.fill == "red"

    # Push modify
    await db_batcher.push("modify", { "board_id": "default",
        "id": "test_shape_1",
        "left": 50,
        "fill": "blue"
    })

    # Process batch
    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_1"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.left == 50
        assert shape.fill == "blue"

    # Push remove
    await db_batcher.push("remove", { "board_id": "default",
        "id": "test_shape_1"
    })

    # Process batch
    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_1"))
        shape = result.scalars().first()
        assert shape is None

@pytest.mark.asyncio
async def test_batch_merge(setup_db_sync):
    # Add then immediately modify before batch processes
    await db_batcher.push("add", { "board_id": "default",
        "id": "test_shape_2",
        "type": "rect",
        "left": 10,
        "top": 20,
        "width": 100,
        "height": 50,
        "fill": "red",
        "z_index": 1
    })

    await db_batcher.push("modify", { "board_id": "default",
        "id": "test_shape_2",
        "left": 50,
        "fill": "blue"
    })

    # Process batch
    await db_batcher.process_batch()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Shape).filter(Shape.id == "test_shape_2"))
        shape = result.scalars().first()
        assert shape is not None
        assert shape.type == "rect"
        assert shape.left == 50
        assert shape.top == 20
        assert shape.fill == "blue"

@pytest.mark.asyncio
async def test_batch_merge_conditions(setup_db_sync):
    from src.main import db_batcher
    # Test pushing without id
    await db_batcher.push("add", {})

    # Test modify modifying modify
    await db_batcher.push("modify", { "board_id": "default",
        "id": "test_shape_3",
        "left": 10
    })
    await db_batcher.push("modify", { "board_id": "default",
        "id": "test_shape_3",
        "top": 20
    })

    # Test remove then add/modify
    await db_batcher.push("remove", { "board_id": "default", "id": "test_shape_4" })
    await db_batcher.push("add", { "board_id": "default", "id": "test_shape_4", "type": "rect" })

    # Test remove then something else
    await db_batcher.push("add", { "board_id": "default", "id": "test_shape_5", "type": "rect" })
    await db_batcher.push("remove", { "board_id": "default", "id": "test_shape_5" })

    await db_batcher.process_batch()

@pytest.mark.asyncio
async def test_batch_merge_unhandled_action():
    from src.main import db_batcher
    # Test pushing an unhandled action combo
    await db_batcher.push("add", { "board_id": "default", "id": "test_shape_10", "type": "rect" })
    await db_batcher.push("some_unknown_action", { "board_id": "default", "id": "test_shape_10" })
    await db_batcher.process_batch()
