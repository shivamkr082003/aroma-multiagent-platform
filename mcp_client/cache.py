"""Small async cache for tools discovered from a user's MCP configuration."""

import asyncio
import hashlib
import json
import time


class ToolCache:
    def __init__(self, ttl_seconds: int = 300):
        self._entries: dict[str, tuple[str, float, list]] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def _fingerprint(config: dict) -> str:
        return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()

    async def get(self, user_id: str, config: dict) -> list | None:
        async with self._lock:
            entry = self._entries.get(user_id)
            if not entry:
                return None
            fingerprint, created_at, tools = entry
            if fingerprint != self._fingerprint(config) or time.monotonic() - created_at > self._ttl_seconds:
                self._entries.pop(user_id, None)
                return None
            return tools

    async def put(self, user_id: str, config: dict, tools: list) -> None:
        async with self._lock:
            self._entries[user_id] = (self._fingerprint(config), time.monotonic(), tools)

    async def invalidate(self, user_id: str) -> None:
        async with self._lock:
            self._entries.pop(user_id, None)

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()


tool_cache = ToolCache()
