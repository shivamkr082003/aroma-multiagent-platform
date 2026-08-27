"""REST endpoints for user-managed MCP server configurations."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from db import SessionLocal
from . import crud
from .manager import mcp_manager
from .schemas import MCPServerCreate, MCPServerResponse, MCPServerTestResponse, MCPServerUpdate, MCPToolInfo

mcp_router = APIRouter(prefix="/mcp", tags=["MCP Servers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@mcp_router.post("/servers", response_model=MCPServerResponse, status_code=201)
async def create_server(data: MCPServerCreate, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    server = crud.create_server(db, user_id, data)
    await mcp_manager.invalidate_cache(user_id)
    return server


@mcp_router.get("/servers", response_model=list[MCPServerResponse])
def list_servers(user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    return crud.list_servers(db, user_id)


@mcp_router.get("/servers/{server_id}", response_model=MCPServerResponse)
def get_server(server_id: str, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    return crud.get_server(db, server_id, user_id)


@mcp_router.put("/servers/{server_id}", response_model=MCPServerResponse)
async def update_server(server_id: str, data: MCPServerUpdate, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    server = crud.update_server(db, server_id, user_id, data)
    await mcp_manager.invalidate_cache(user_id)
    return server


@mcp_router.delete("/servers/{server_id}", status_code=204)
async def delete_server(server_id: str, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    crud.delete_server(db, server_id, user_id)
    await mcp_manager.invalidate_cache(user_id)
    return Response(status_code=204)


@mcp_router.post("/servers/{server_id}/enable", response_model=MCPServerResponse)
async def enable_server(server_id: str, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    server = crud.set_enabled(db, server_id, user_id, True)
    await mcp_manager.invalidate_cache(user_id)
    return server


@mcp_router.post("/servers/{server_id}/disable", response_model=MCPServerResponse)
async def disable_server(server_id: str, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    server = crud.set_enabled(db, server_id, user_id, False)
    await mcp_manager.invalidate_cache(user_id)
    return server


@mcp_router.post("/servers/{server_id}/test", response_model=MCPServerTestResponse)
async def test_server(server_id: str, user_id: str = Query("demo_user"), db: Session = Depends(get_db)):
    server = crud.get_server(db, server_id, user_id)
    try:
        config = server.to_client_config()
    except ValueError as exc:
        return MCPServerTestResponse(reachable=False, server_name=server.name, error=str(exc))
    reachable, tools, error = await mcp_manager.test_server(server.name, config)
    return MCPServerTestResponse(reachable=reachable, server_name=server.name, tools=[MCPToolInfo(**tool) for tool in tools], error=error)
