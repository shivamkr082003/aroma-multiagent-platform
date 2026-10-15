"""Pydantic request and response schemas for MCP server management."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .security import mask


class MCPServerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    transport: str
    url: Optional[str] = None
    headers: Optional[dict] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[dict[str, str]] = None

    @model_validator(mode="after")
    def validate_fields(self):
        self.transport = self.transport.lower().strip()
        if self.transport not in ("http", "sse", "stdio"):
            raise ValueError("transport must be 'http', 'sse', or 'stdio'.")
        if self.transport in ("http", "sse"):
            if not self.url or not self.url.startswith(("http://", "https://")):
                raise ValueError("HTTP/SSE transport requires an http(s) URL.")
            if self.command or self.args:
                raise ValueError("HTTP/SSE transport does not accept command or args.")
        elif not self.command:
            raise ValueError("STDIO transport requires command.")
        elif self.url:
            raise ValueError("STDIO transport does not accept url.")
        return self


class MCPServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    transport: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[dict] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[dict[str, str]] = None
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def validate_transport(self):
        if self.transport is not None:
            self.transport = self.transport.lower().strip()
            if self.transport not in ("http", "sse", "stdio"):
                raise ValueError("transport must be 'http', 'sse', or 'stdio'.")
        if self.url is not None and not self.url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://.")
        return self


class MCPServerResponse(BaseModel):
    id: str
    user_id: str
    name: str
    transport: str
    url: Optional[str] = None
    headers: Optional[dict] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[dict[str, str]] = None
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

    # Header and env values usually hold API keys; never send them back.
    @field_validator("headers", "env")
    @classmethod
    def mask_secrets(cls, value):
        return mask(value)


class MCPConfigResponse(BaseModel):
    stdio_allowed: bool
    stdio_allowed_commands: list[str]


class MCPToolInfo(BaseModel):
    name: str
    description: Optional[str] = None


class MCPServerTestResponse(BaseModel):
    reachable: bool
    server_name: str
    tools: list[MCPToolInfo] = Field(default_factory=list)
    error: Optional[str] = None
