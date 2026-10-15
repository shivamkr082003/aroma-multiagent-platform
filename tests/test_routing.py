from types import SimpleNamespace

import pytest

import Agent.agent as agent
import rag_store


def base_state(**overrides):
    state = {
        "user_msg": "hello", "session_id": "s1", "file_id": None, "user_id": "u1",
        "has_urls": False, "needs_search": False, "has_docs": False,
        "rag_context": "", "search_context": "", "reply": "",
    }
    state.update(overrides)
    return state


@pytest.fixture
def router_llm_says(monkeypatch):
    def configure(flags_json: str):
        monkeypatch.setattr(agent, "router_llm", SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=flags_json)))
    return configure


def test_plain_chat_skips_retrieval(router_llm_says, monkeypatch):
    # The LLM guessing "has_docs" must not force retrieval when nothing was uploaded.
    router_llm_says('{"has_docs": true, "needs_search": false, "has_urls": false}')
    monkeypatch.setattr(agent, "session_has_docs", lambda *args: False)
    state = base_state(**agent.router_node(base_state()))
    assert state["has_docs"] is False
    assert agent.route_after_router(state) == "answer_node"


def test_chat_with_uploaded_document_goes_to_rag(router_llm_says, monkeypatch):
    router_llm_says('{"needs_search": false}')
    seen = {}

    def has_docs(session_id, user_id, project_id=None):
        seen["args"] = (session_id, user_id, project_id)
        return True

    monkeypatch.setattr(agent, "session_has_docs", has_docs)
    state = base_state(**agent.router_node(base_state()))
    assert seen["args"] == ("s1", "u1", None)
    assert agent.route_after_router(state) == "rag_node"


def test_file_id_goes_to_rag_without_lookup(router_llm_says, monkeypatch):
    router_llm_says("{}")
    monkeypatch.setattr(agent, "session_has_docs", lambda *a: pytest.fail("lookup not needed"))
    state = base_state(**agent.router_node(base_state(file_id="f1")))
    assert agent.route_after_router(state) == "rag_node"


def test_search_still_routes_to_web(router_llm_says, monkeypatch):
    router_llm_says('{"needs_search": true}')
    monkeypatch.setattr(agent, "session_has_docs", lambda *a: False)
    state = base_state(**agent.router_node(base_state(user_msg="latest news on AI")))
    assert agent.route_after_router(state) == "web_search_node"


@pytest.mark.parametrize("env,expected", [
    ({}, "docs_bge_small_en_v1_5"),
    ({"LOCAL_EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"}, "docs_all_minilm_l6_v2"),
    ({"EMBEDDING_PROVIDER": "openai"}, "docs"),
    ({"QDRANT_COLLECTION": "custom"}, "custom"),
])
def test_collection_name_per_embedding_model(monkeypatch, env, expected):
    for key in ("EMBEDDING_PROVIDER", "LOCAL_EMBEDDING_MODEL", "QDRANT_COLLECTION"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert rag_store.collection_name() == expected
