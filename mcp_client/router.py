"""REST endpoints for user-managed MCP server configurations."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from db import get_db
from models.user import User
from . import crud
from .manager import mcp_manager
from .schemas import (
    MCPConfigResponse,
    MCPServerCreate,
    MCPServerResponse,
    MCPServerTestResponse,
    MCPServerUpdate,
    MCPToolInfo,
)
from .security import check_transport_allowed, stdio_allowed, stdio_allowed_commands

mcp_router = APIRouter(prefix="/mcp", tags=["MCP Servers"])


@mcp_router.get("/config", response_model=MCPConfigResponse)
def get_config():
    """What the backend allows, so the UI can hide unavailable transports."""
    allowed = stdio_allowed()
    return MCPConfigResponse(stdio_allowed=allowed, stdio_allowed_commands=stdio_allowed_commands() if allowed else [])


@mcp_router.post("/servers", response_model=MCPServerResponse, status_code=201)
async def create_server(data: MCPServerCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = crud.create_server(db, user.id, data)
    await mcp_manager.invalidate_cache(user.id)
    return server


@mcp_router.get("/servers", response_model=list[MCPServerResponse])
def list_servers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.list_servers(db, user.id)


@mcp_router.get("/servers/{server_id}", response_model=MCPServerResponse)
def get_server(server_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.get_server(db, server_id, user.id)


@mcp_router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_server(server_id: str, data: MCPServerUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = crud.update_server(db, server_id, user.id, data)
    await mcp_manager.invalidate_cache(user.id)
    return server


@mcp_router.delete("/servers/{server_id}", status_code=204)
async def delete_server(server_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    crud.delete_server(db, server_id, user.id)
    await mcp_manager.invalidate_cache(user.id)
    return Response(status_code=204)


@mcp_router.post("/servers/{server_id}/enable", response_model=MCPServerResponse)
async def enable_server(server_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = crud.set_enabled(db, server_id, user.id, True)
    await mcp_manager.invalidate_cache(user.id)
    return server


@mcp_router.post("/servers/{server_id}/disable", response_model=MCPServerResponse)
async def disable_server(server_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = crud.set_enabled(db, server_id, user.id, False)
    await mcp_manager.invalidate_cache(user.id)
    return server


@mcp_router.post("/servers/{server_id}/test", response_model=MCPServerTestResponse)
async def test_server(server_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = crud.get_server(db, server_id, user.id)
    try:
        check_transport_allowed(server.transport, server.command)
        config = server.to_client_config()
    except ValueError as exc:
        return MCPServerTestResponse(reachable=False, server_name=server.name, error=str(exc))
    reachable, tools, error = await mcp_manager.test_server(server.name, config)
    return MCPServerTestResponse(reachable=reachable, server_name=server.name, tools=[MCPToolInfo(**tool) for tool in tools], error=error)
