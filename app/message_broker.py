from typing import Any, Optional
import json
from redis.asyncio import Redis, from_url
from pydantic import BaseModel

class MessageBroker:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None

    async def connect(self):
        self.redis = await from_url(self.redis_url, encoding="utf-8", decode_responses=True)

    async def disconnect(self):
        if self.redis:
            await self.redis.close()

    async def publish(self, channel: str, message: Any):
        if not self.redis:
            await self.connect()
        
        if isinstance(message, (dict, list)):
            message = json.dumps(message)
        elif isinstance(message, BaseModel):
            message = message.model_dump_json()
        
        await self.redis.publish(channel, message)

    async def subscribe(self, channel: str):
        if not self.redis:
            await self.connect()
        
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def get_message(self, pubsub) -> Optional[dict]:
        message = await pubsub.get_message(ignore_subscribe_messages=True)
        if message and message["type"] == "message":
            try:
                return json.loads(message["data"])
            except json.JSONDecodeError:
                return message["data"]
        return None

    async def set(self, key: str, value: Any, expire: Optional[int] = None):
        if not self.redis:
            await self.connect()
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        elif isinstance(value, BaseModel):
            value = value.model_dump_json()
        
        await self.redis.set(key, value)
        if expire:
            await self.redis.expire(key, expire)

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            await self.connect()
        
        value = await self.redis.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None 