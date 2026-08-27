"""Load enabled MCP tools and isolate connection failures from chat requests."""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from .cache import tool_cache

logger = logging.getLogger("aroma.mcp")


class MCPManager:
    async def load_tools(self, user_id: str, db: Optional[Session] = None) -> list:
        owns_session = db is None
        if owns_session:
            from db import SessionLocal
            db = SessionLocal()
        try:
            from .models import MCPServer
            servers = db.query(MCPServer).filter(MCPServer.user_id == user_id, MCPServer.enabled.is_(True)).all()
            config = {server.name: server.to_client_config() for server in servers}
            if not config:
                return []
            cached = await tool_cache.get(user_id, config)
            if cached is not None:
                return cached

            tools: list = []
            for name, server_config in config.items():
                try:
                    tools.extend(await self._load_one(name, server_config))
                except Exception as exc:
                    logger.warning("MCP server '%s' is unavailable: %s", name, exc)
            await tool_cache.put(user_id, config, tools)
            return tools
        except Exception as exc:
            logger.exception("Could not load MCP tools for user %s: %s", user_id, exc)
            return []
        finally:
            if owns_session:
                db.close()

    @staticmethod
    async def _load_one(name: str, config: dict) -> list:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        return await MultiServerMCPClient({name: config}).get_tools()

    async def test_server(self, name: str, config: dict) -> tuple[bool, list[dict], str | None]:
        try:
            tools = await self._load_one(name, config)
            return True, [{"name": tool.name, "description": getattr(tool, "description", None)} for tool in tools], None
        except Exception as exc:
            logger.info("MCP test for '%s' failed: %s", name, exc)
            return False, [], str(exc)

    async def invalidate_cache(self, user_id: str) -> None:
        await tool_cache.invalidate(user_id)

    async def shutdown(self) -> None:
        await tool_cache.clear()


mcp_manager = MCPManager()
