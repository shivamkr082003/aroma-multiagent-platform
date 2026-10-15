"""CRUD helpers for MCP server configuration records."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import MCPServer
from .schemas import MCPServerCreate, MCPServerUpdate
from .security import MCPPolicyError, check_transport_allowed, ensure_can_store_secrets, merge_masked


def _get(db: Session, server_id: str, user_id: str) -> MCPServer:
    server = db.query(MCPServer).filter_by(id=server_id, user_id=user_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found.")
    return server


def _check_name(db: Session, user_id: str, name: str, exclude_id: str | None = None):
    query = db.query(MCPServer).filter_by(user_id=user_id, name=name)
    if exclude_id:
        query = query.filter(MCPServer.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An MCP server with this name already exists.")


def _check_policy(transport: str, command: str | None, headers: dict | None, env: dict | None) -> None:
    try:
        check_transport_allowed(transport, command)
    except MCPPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    try:
        ensure_can_store_secrets(headers, env)
    except MCPPolicyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def create_server(db: Session, user_id: str, data: MCPServerCreate) -> MCPServer:
    _check_name(db, user_id, data.name)
    _check_policy(data.transport, data.command, data.headers, data.env)
    server = MCPServer(user_id=user_id, **data.model_dump())
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


def list_servers(db: Session, user_id: str) -> list[MCPServer]:
    return db.query(MCPServer).filter_by(user_id=user_id).order_by(MCPServer.created_at.desc()).all()


def get_server(db: Session, server_id: str, user_id: str) -> MCPServer:
    return _get(db, server_id, user_id)


def update_server(db: Session, server_id: str, user_id: str, data: MCPServerUpdate) -> MCPServer:
    server = _get(db, server_id, user_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("name") and values["name"] != server.name:
        _check_name(db, user_id, values["name"], server_id)
    # Clients only ever see masked secrets, so a masked value means "unchanged".
    for key in ("headers", "env"):
        if key in values:
            values[key] = merge_masked(values[key], getattr(server, key))
    transport = values.get("transport", server.transport)
    url = values.get("url", server.url)
    command = values.get("command", server.command)
    if transport in ("http", "sse") and not url:
        raise HTTPException(status_code=422, detail="HTTP/SSE transport requires url.")
    if transport == "stdio" and not command:
        raise HTTPException(status_code=422, detail="STDIO transport requires command.")
    _check_policy(transport, command, values.get("headers", server.headers), values.get("env", server.env))
    for key, value in values.items():
        setattr(server, key, value)
    db.commit()
    db.refresh(server)
    return server


def delete_server(db: Session, server_id: str, user_id: str) -> None:
    db.delete(_get(db, server_id, user_id))
    db.commit()


def set_enabled(db: Session, server_id: str, user_id: str, enabled: bool) -> MCPServer:
    server = _get(db, server_id, user_id)
    if enabled:
        _check_policy(server.transport, server.command, None, None)
    server.enabled = enabled
    db.commit()
    db.refresh(server)
    return server
