from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

import Agent.agent as agent
from mcp_client.manager import mcp_manager


async def collect(stream):
    return [event async for event in stream]


def patch_common(monkeypatch, *, has_docs: bool):
    monkeypatch.setattr(agent, "router_llm", SimpleNamespace(invoke=lambda m: SimpleNamespace(content="{}")))
    monkeypatch.setattr(agent, "session_has_docs", lambda *a: has_docs)
    monkeypatch.setattr(agent, "get_chat_history", lambda sid: [])
    monkeypatch.setattr(agent, "save_chat_history", lambda sid, h: None)

    async def no_tools(user_id, db=None):
        return []

    monkeypatch.setattr(mcp_manager, "load_tools", no_tools)


async def test_stream_emits_status_tokens_then_done(monkeypatch):
    patch_common(monkeypatch, has_docs=False)
    monkeypatch.setattr(agent, "llm", GenericFakeChatModel(messages=iter([AIMessage(content="Hello there friend")])))

    events = await collect(agent.achat_stream("hi", "s1", user_id="u1"))
    kinds = [e["type"] for e in events]

    assert kinds[0] == "status" and kinds[-1] == "done"
    assert kinds.count("token") > 1  # streamed in pieces, not one blob
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello there friend"
    assert events[-1] == {"type": "done", "response": "Hello there friend", "sources": []}


async def test_document_answers_get_numbered_citations(monkeypatch):
    patch_common(monkeypatch, has_docs=True)
    docs = [
        Document(page_content="Team lead: Ananya Rao", metadata={"file_name": "zephyr.pdf", "page": 0}),
        Document(page_content="Budget: 42,500 rupees", metadata={"file_name": "zephyr.pdf", "page": 1}),
    ]
    monkeypatch.setattr(agent, "get_vectorstore", lambda: None)
    monkeypatch.setattr(agent, "retrieve", lambda query, flt, **kw: docs)

    prompts = []

    class RecordingLLM(GenericFakeChatModel):
        def _stream(self, messages, *args, **kwargs):
            prompts.append(messages[-1].content)
            yield from super()._stream(messages, *args, **kwargs)

    monkeypatch.setattr(agent, "llm", RecordingLLM(messages=iter([AIMessage(content="Ananya Rao leads it [1].")])))

    events = await collect(agent.achat_stream("who leads it?", "s1", user_id="u1"))
    done = events[-1]

    assert [s["id"] for s in done["sources"]] == [1, 2]
    assert done["sources"][0] == {"id": 1, "type": "document", "title": "zephyr.pdf", "page": 1,
                                  "snippet": "Team lead: Ananya Rao"}
    assert any(e["type"] == "sources" for e in events)  # shown before the answer finishes
    assert "[1] (zephyr.pdf, page 1)" in prompts[0] and "[2] (zephyr.pdf, page 2)" in prompts[0]
    assert "cite it inline" in prompts[0]


async def test_errors_end_the_stream_cleanly(monkeypatch):
    patch_common(monkeypatch, has_docs=False)

    def boom(*args, **kwargs):
        raise RuntimeError("groq down")

    monkeypatch.setattr(agent, "router_llm", SimpleNamespace(invoke=boom))
    events = await collect(agent.achat_stream("hi", "s1", user_id="u1"))
    assert events[-1]["type"] == "error"


def test_parse_search_results():
    output = "Title: Next.js 16\nURL: https://nextjs.org/blog/next-16\nSnippet: ...\n\n----\nTitle: Proxy\nURL: https://nextjs.org/docs/proxy\nSnippet: ..."
    assert agent._parse_search_results([ToolMessage(content=output, tool_call_id="1")]) == [
        ("Next.js 16", "https://nextjs.org/blog/next-16"),
        ("Proxy", "https://nextjs.org/docs/proxy"),
    ]
