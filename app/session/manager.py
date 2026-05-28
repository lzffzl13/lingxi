import json
from datetime import datetime
from typing import Optional

import redis.asyncio as redis

from app.config import Settings
from app.models.message import Message, SessionSlot


class SessionManager:
    """Manages session data in Redis: history and slots."""

    def __init__(self, redis_client: redis.Redis, config: Settings):
        self.redis = redis_client
        self.ttl = config.SESSION_TTL
        self.max_history = config.MAX_HISTORY_LENGTH

    def _key_history(self, session_id: str) -> str:
        return f"session:{session_id}:history"

    def _key_slots(self, session_id: str) -> str:
        return f"session:{session_id}:slots"

    async def get_history(self, session_id: str) -> list[Message]:
        """Get message history for a session."""
        key = self._key_history(session_id)
        items = await self.redis.lrange(key, 0, -1)
        messages = []
        for item in items:
            data = json.loads(item)
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            messages.append(Message(**data))
        return messages

    async def append_message(self, session_id: str, message: Message) -> None:
        """Append a message to session history and trim if needed."""
        key = self._key_history(session_id)
        data = message.model_dump_json()
        await self.redis.rpush(key, data)
        await self.redis.ltrim(key, -self.max_history, -1)
        await self._refresh_ttl(session_id)

    async def get_slots(self, session_id: str) -> SessionSlot:
        """Get session slots."""
        key = self._key_slots(session_id)
        data = await self.redis.hgetall(key)
        if not data:
            return SessionSlot()
        # Parse JSON values
        parsed = {}
        for k, v in data.items():
            try:
                parsed[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                parsed[k] = v
        return SessionSlot(**parsed)

    async def update_slot(self, session_id: str, **kwargs) -> SessionSlot:
        """Update session slots with given key-value pairs."""
        key = self._key_slots(session_id)
        mapping = {k: json.dumps(v) for k, v in kwargs.items()}
        await self.redis.hset(key, mapping=mapping)
        await self._refresh_ttl(session_id)
        return await self.get_slots(session_id)

    async def clear_session(self, session_id: str) -> None:
        """Delete all session data."""
        await self.redis.delete(
            self._key_history(session_id),
            self._key_slots(session_id),
        )

    async def _refresh_ttl(self, session_id: str) -> None:
        """Refresh TTL for all session keys."""
        await self.redis.expire(self._key_history(session_id), self.ttl)
        await self.redis.expire(self._key_slots(session_id), self.ttl)
