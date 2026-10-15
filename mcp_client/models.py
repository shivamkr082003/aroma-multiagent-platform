"""Database model for a user-configured MCP server."""

import uuid

from sqlalchemy import Boolean, Column, JSON, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.sql import func

from db import Base
from .security import EncryptedJSON


class MCPServer(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_mcp_servers_user_name"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    transport = Column(String, nullable=False)  # http, sse, or stdio
    url = Column(Text, nullable=True)
    headers = Column(EncryptedJSON, nullable=True)  # encrypted at rest
    command = Column(String, nullable=True)
    args = Column(JSON, nullable=True)
    env = Column(EncryptedJSON, nullable=True)  # encrypted at rest
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    def to_client_config(self) -> dict:
        if self.transport in ("http", "sse"):
            if not self.url:
                raise ValueError(f"{self.transport.upper()} transport requires a URL.")
            config = {"transport": self.transport, "url": self.url}
            if self.headers:
                config["headers"] = self.headers
            return config
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("STDIO transport requires a command.")
            config = {"transport": "stdio", "command": self.command}
            if self.args:
                config["args"] = self.args
            if self.env:
                config["env"] = self.env
            return config
        raise ValueError(f"Unsupported MCP transport: {self.transport}")
