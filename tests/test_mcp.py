import json
import os
import sys
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGenerationChunk
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db as db_module
from auth.deps import get_current_user
from db import Base
from mcp_client import router as router_module
from mcp_client.manager import mcp_manager
from mcp_client.models import MCPServer
from mcp_client.security import MASK

DUMMY_SERVER = os.path.join(os.path.dirname(__file__), "dummy_mcp_server.py")


@pytest.fixture(autouse=True)
def mcp_env(monkeypatch):
    monkeypatch.delenv("MCP_ALLOW_STDIO", raising=False)
    monkeypatch.delenv("MCP_STDIO_ALLOWED_COMMANDS", raising=False)
    monkeypatch.setenv("MCP_SECRET_KEY", Fernet.generate_key().decode())


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[MCPServer.__table__])
    return sessionmaker(bind=engine)


@pytest.fixture
def client(session_factory):
    app = FastAPI()
    app.include_router(router_module.mcp_router)

    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[db_module.get_db] = get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="u1")
    return TestClient(app)


def http_server(**extra):
    return {"name": "remote", "transport": "http", "url": "https://mcp.example/mcp", **extra}


def stdio_server(command="npx"):
    return {"name": "local", "transport": "stdio", "command": command, "args": ["-y", "some-server"]}


# ===========================
#  STDIO POLICY
# ===========================
def test_stdio_disabled_by_default(client):
    response = client.post("/mcp/servers", json=stdio_server())
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]
    assert client.get("/mcp/config").json() == {"stdio_allowed": False, "stdio_allowed_commands": []}


@pytest.mark.parametrize("command,status", [("npx", 201), ("bash", 403), ("/usr/bin/npx", 403)])
def test_stdio_allowlist(client, monkeypatch, command, status):
    monkeypatch.setenv("MCP_ALLOW_STDIO", "true")
    monkeypatch.setenv("MCP_STDIO_ALLOWED_COMMANDS", "npx,uvx")
    assert client.post("/mcp/servers", json=stdio_server(command)).status_code == status


def test_switching_to_disallowed_stdio_via_update_is_rejected(client):
    server = client.post("/mcp/servers", json=http_server()).json()
    response = client.put(f"/mcp/servers/{server['id']}", json={"transport": "stdio", "command": "bash", "url": None})
    assert response.status_code == 403


async def test_manager_skips_stdio_rows_when_disabled(session_factory, monkeypatch):
    # Saved while STDIO was allowed; the policy is now off again.
    db = session_factory()
    db.add(MCPServer(user_id="u1", name="local", transport="stdio", command=sys.executable, args=[DUMMY_SERVER]))
    db.commit()

    async def must_not_connect(name, config):
        raise AssertionError("disallowed server was started")

    monkeypatch.setattr(mcp_manager, "_load_one", must_not_connect)
    await mcp_manager.invalidate_cache("u1")
    assert await mcp_manager.load_tools("u1", db) == []


# ===========================
#  SECRETS
# ===========================
def test_secrets_are_masked_and_encrypted(client, session_factory):
    response = client.post("/mcp/servers", json=http_server(headers={"Authorization": "Bearer sk-live-123"}))
    assert response.status_code == 201
    assert response.json()["headers"] == {"Authorization": MASK}
    assert client.get("/mcp/servers").json()[0]["headers"] == {"Authorization": MASK}

    with session_factory() as db:
        raw = db.execute(text("select headers from mcp_servers")).scalar_one()
        assert "sk-live-123" not in raw and "__enc__" in raw
        assert db.query(MCPServer).one().headers == {"Authorization": "Bearer sk-live-123"}


def test_update_keeps_masked_values_and_replaces_new_ones(client, session_factory):
    server = client.post("/mcp/servers", json=http_server(headers={"Authorization": "Bearer old", "X-Team": "a"})).json()
    response = client.put(f"/mcp/servers/{server['id']}", json={"headers": {"Authorization": MASK, "X-Team": "b"}})
    assert response.status_code == 200

    with session_factory() as db:
        assert db.query(MCPServer).one().headers == {"Authorization": "Bearer old", "X-Team": "b"}


def test_secrets_require_key(client, monkeypatch):
    monkeypatch.delenv("MCP_SECRET_KEY")
    response = client.post("/mcp/servers", json=http_server(headers={"Authorization": "Bearer x"}))
    assert response.status_code == 400
    assert "MCP_SECRET_KEY" in response.json()["detail"]
    # Servers without secrets still work without a key.
    assert client.post("/mcp/servers", json=http_server()).status_code == 201


# ===========================
#  AGENT USES MCP TOOLS
# ===========================
class ToolCallingFakeLLM(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        # The stock fake model drops tool calls when streaming; send each scripted reply as one chunk.
        message = next(self.messages)
        yield ChatGenerationChunk(message=AIMessageChunk(
            content=message.content,
            tool_call_chunks=[
                {"name": call["name"], "args": json.dumps(call["args"]), "id": call["id"], "index": i}
                for i, call in enumerate(message.tool_calls)
            ],
        ))


async def test_answer_node_calls_async_mcp_tool(monkeypatch):
    """MCP adapter tools are async-only; the agent must await them, not call them sync."""
    import Agent.agent as agent
    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def load_tools(user_id, db=None):
        config = {"dummy": {"transport": "stdio", "command": sys.executable, "args": [DUMMY_SERVER]}}
        return await MultiServerMCPClient(config).get_tools()

    monkeypatch.setattr(mcp_manager, "load_tools", load_tools)
    monkeypatch.setattr(agent, "get_chat_history", lambda session_id: [])
    monkeypatch.setattr(agent, "save_chat_history", lambda session_id, history: None)
    monkeypatch.setattr(agent, "llm", ToolCallingFakeLLM(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "add", "args": {"a": 2, "b": 40}, "id": "call-1"}]),
        AIMessage(content="The answer is 42."),
    ])))

    real_create = agent.create_react_agent
    tool_results = []

    def create_and_record(llm, tools):
        graph = real_create(llm, tools=tools)
        original = graph.astream

        async def astream(*args, **kwargs):
            async for chunk, meta in original(*args, **kwargs):
                if isinstance(chunk, ToolMessage):
                    tool_results.append(str(chunk.content))
                yield chunk, meta

        graph.astream = astream
        return graph

    monkeypatch.setattr(agent, "create_react_agent", create_and_record)

    state = {
        "user_msg": "What is 2 + 40?", "session_id": "s1", "file_id": None, "user_id": "u1",
        "has_urls": False, "needs_search": False, "has_docs": False,
        "rag_context": "", "search_context": "", "reply": "",
    }
    result = await agent.answer_node(state)

    assert result == {"reply": "The answer is 42."}
    assert len(tool_results) == 1 and "42" in tool_results[0]
