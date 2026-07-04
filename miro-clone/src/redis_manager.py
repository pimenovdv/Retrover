import os
import json
import logging
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.redis = None
        self.pubsub = None
        self.channel = "board_updates"
        self.listen_task = None
        # Reference back to connection manager
        self.conn_manager = None

    async def connect(self):
        try:
            # First try real redis
            import redis.asyncio as aioredis
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            self.redis = aioredis.from_url(redis_url, decode_responses=True)
            await self.redis.ping()
            logger.info(f"Connected to real Redis at {redis_url}")
        except Exception as e:
            logger.warning(f"Failed to connect to real Redis: {e}. Falling back to Fakeredis.")
            import fakeredis.aioredis
            self.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(self.channel)
        logger.info("Subscribed to Redis channel")

    async def start_listening(self, conn_manager):
        self.conn_manager = conn_manager
        import asyncio
        self.listen_task = asyncio.create_task(self._listen())

    async def _listen(self):
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    sender = data.get("sender")
                    board_id = data.get("board_id", "default")
                    # Broadcast to all local connections except sender
                    await self.conn_manager.local_broadcast(board_id, data, exclude=sender)
        except Exception as e:
            logger.error(f"Redis listen error: {e}")

    async def publish(self, message: dict):
        if self.redis:
            await self.redis.publish(self.channel, json.dumps(message))

    async def close(self):
        if self.listen_task:
            self.listen_task.cancel()
        if self.pubsub:
            await self.pubsub.aclose()
        if self.redis:
            await self.redis.aclose()

redis_manager = RedisManager()
