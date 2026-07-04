import pytest
import json
import asyncio
from unittest.mock import MagicMock
from src.redis_manager import RedisManager

@pytest.mark.asyncio
async def test_redis_manager_connects_fakeredis():
    rm = RedisManager()
    await rm.connect()
    assert rm.redis is not None
    assert rm.pubsub is not None
    await rm.close()

@pytest.mark.asyncio
async def test_redis_manager_publish_listen():
    rm = RedisManager()
    await rm.connect()

    mock_conn_manager = MagicMock()
    mock_conn_manager.local_broadcast = MagicMock()

    # Needs to be async mock in python 3.8+
    async def mock_local_broadcast(*args, **kwargs):
        mock_conn_manager.local_broadcast_called = True
        mock_conn_manager.call_args = (args, kwargs)

    mock_conn_manager.local_broadcast = mock_local_broadcast

    await rm.start_listening(mock_conn_manager)

    # Wait a bit for listener to start
    await asyncio.sleep(0.1)

    # Publish a message
    test_msg = {"type": "update", "action": "cursor", "sender": "test_user"}
    await rm.publish(test_msg)

    # Wait for listener to receive
    await asyncio.sleep(0.2)

    assert getattr(mock_conn_manager, 'local_broadcast_called', False) is True
    args, kwargs = mock_conn_manager.call_args
    assert args[0] == "default"
    assert args[1] == test_msg
    assert kwargs["exclude"] == "test_user"

    await rm.close()
