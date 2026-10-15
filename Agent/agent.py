from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import logging
import re
import json
import operator
from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from urllib.parse import urlparse

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from redis_client import get_chat_history, save_chat_history
from tools import web_search, scrape_url
from rag_store import collection_name, get_vectorstore, qdrant_client, session_has_docs
from retrieval import current_mode, retrieve, scope_filter

# ===========================
#  SETUP
# ===========================

llm = ChatOpenAI(
    model="openai/gpt-oss-120b",
    temperature=0.7,
    timeout=60,
    max_retries=2,
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

router_llm = ChatOpenAI(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+")

# Matches bare domains with no scheme, e.g. "leetcode.com/u/foo",
# "github.com/foo", "linkedin.com/in/foo" — common in resumes/PDFs where
# links are printed as plain text rather than clickable hyperlinks.
#
# Restricted to a whitelist of real TLDs (not "any letters") so resume
# text like "React.js", "Node.js", "B.Tech", "CodeHelp.in" stops being
# misread as a domain — those have real-looking endings but aren't URLs.
COMMON_TLDS = (
    "com|org|net|io|co|in|dev|app|me|ai|edu|gov|info|biz|xyz|"
    "us|uk|ca|de|fr|jp|cn|au|nz|br|ru|es|it|nl|se|no|fi|pl|ch"
)

BARE_DOMAIN_PATTERN = re.compile(
    r"\b(?:[a-zA-Z0-9-]+\.)+(?:" + COMMON_TLDS + r")\b(?:/[^\s)\]>\"']*)?",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    """
    Find both full URLs (https://...) and bare domains (leetcode.com/...)
    in a block of text, normalizing bare domains to https://.
    Returns a deduped, order-preserving list.
    """
    if not text:
        return []

    found = []

    # Full URLs first
    for m in URL_PATTERN.finditer(text):
        found.append(m.group(0).rstrip(".,;:!?"))

    # Bare domains — skip any span that's already inside a matched full URL
    full_spans = [m.span() for m in URL_PATTERN.finditer(text)]

    def _inside_full_url(start: int, end: int) -> bool:
        return any(fs <= start and end <= fe for fs, fe in full_spans)

    for m in BARE_DOMAIN_PATTERN.finditer(text):
        if _inside_full_url(*m.span()):
            continue
        candidate = m.group(0).rstrip(".,;:!?")
        found.append("https://" + candidate)

    # Dedupe, preserve order
    seen = set()
    deduped = []
    for u in found:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped

SYSTEM_PROMPT = """
You are an expert AI assistant named Aroma.

Follow these rules strictly:

1. Structure & Clarity
- Use headings and bullet points
- Keep answers well-structured and easy to scan

2. Explanation Style
- Start simple → then go deeper
- Use examples for clarity

3. Tone
- Professional but conversational

4. Depth Control
- Simple → short
- Technical → detailed

5. Code
- Clean with short comments

6. Key Insights
- Add tips when useful

7. Avoid
- Long messy paragraphs

8. If unsure
- Say "I don't know"

9. Context Usage
- If "Scraped URL Content" or "Web Search Results" are present below, you DID retrieve that page/data — never claim you "cannot access external websites" or "cannot browse the internet". Just answer using the provided content.
- Only say you can't retrieve something if no such context block was actually given to you.
"""

ROUTER_PROMPT = """You are a query classifier. Given a user message, output ONLY a JSON object:

{
  "has_urls": true/false,
  "needs_search": true/false,
  "has_docs": true/false
}

Rules:
- has_urls: true if the message contains any http/https URL
- needs_search: true for news, prices, weather, sports, recent/live info
- has_docs: true if user references "the document", "the file", "the PDF", "uploaded", "the link in it", etc.
Return ONLY raw JSON. No markdown. No explanation.
"""


# ===========================
#  GRAPH STATE
#
#  KEY DESIGN RULES:
#  - Read-only inputs (user_msg, session_id, file_id, flags):
#      Plain types — only the router writes them, so no conflict.
#  - Parallel-written accumulator fields (rag_context, search_context):
#      Annotated with operator.add so LangGraph concatenates
#      contributions from simultaneous nodes instead of conflicting.
#  - Nodes return ONLY the keys they own — never {**state, ...}
#
#  ROUTING SHAPE (changed):
#  router_node
#     ├── has_docs (upload)  -> rag_node -> route_after_rag -> {url_scrape_node | web_search_node | answer_node}
#     ├── has_urls (no docs)-> url_scrape_node -> answer_node
#     ├── needs_search only -> web_search_node -> answer_node
#     └── nothing           -> answer_node
#
#  We no longer fan out rag_node + url_scrape_node in parallel, because a
#  URL referenced by the user may live INSIDE the document text itself
#  (e.g. a PDF containing a link). We must read the document first, look
#  for URLs in both the user's message AND the retrieved doc chunks, and
#  only then decide whether to scrape.
# ===========================
class ChatState(TypedDict):
    # ── Immutable inputs (written once by caller / router) ──
    user_msg:   str
    session_id: str
    file_id:    str | None
    user_id:    str
    project_id: str | None   # chats in a project also search the project's documents

    # ── Routing flags (written only by router_node) ──
    has_urls:     bool
    needs_search: bool
    has_docs:     bool

    # ── Accumulators ──
    #    operator.add on str  →  concatenation
    rag_context:    Annotated[str, operator.add]
    search_context: Annotated[str, operator.add]
    # Citations shown under the answer; numbered in the order nodes add them.
    sources:        Annotated[list, operator.add]

    # ── Final output (written only by answer_node) ──
    reply: str


# ===========================
#  LIVE EVENTS (for /chat/stream)
#  No-ops when the graph runs without streaming (ainvoke).
# ===========================
def _emit(event: dict) -> None:
    try:
        get_stream_writer()(event)
    except Exception:
        pass  # called outside a graph run (e.g. a unit test calling a node directly)


def _status(label: str) -> None:
    _emit({"type": "status", "label": label})


def _domain(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.") or url


def _text(content) -> str:
    """Message content can be a string or a list of content parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _parse_search_results(messages: list) -> list[tuple[str, str]]:
    """(title, url) pairs from web_search tool output (see tools.web_search)."""
    found = []
    for message in messages:
        if isinstance(message, ToolMessage):
            found += re.findall(r"Title: (.*)\nURL: (\S+)", _text(message.content))
    return found


# ===========================
#  NODE 1 — ROUTER
# ===========================
def router_node(state: ChatState) -> dict:
    """Classify the message; return ONLY the keys this node owns."""
    _status("Understanding your question…")
    urls_found = bool(extract_urls(state["user_msg"]))

    response = router_llm.invoke([
        SystemMessage(content=ROUTER_PROMPT),
        HumanMessage(content=state["user_msg"]),
    ])

    try:
        flags = json.loads(response.content)
    except Exception:
        flags = {}

    return {
        "has_urls":     flags.get("has_urls",     False) or urls_found,
        "needs_search": flags.get("needs_search", False),
        # Ground truth instead of the LLM's guess: only chats that actually
        # have an uploaded document need the (slower) retrieval step.
        "has_docs":     bool(state.get("file_id"))
                        or session_has_docs(state["session_id"], state.get("user_id", "demo_user"),
                                            state.get("project_id")),
        # Reset accumulators at the start of each request
        "rag_context":    "",
        "search_context": "",
    }


# ===========================
#  ROUTING EDGE — after router
# ===========================
def route_after_router(state: ChatState) -> str:
    """
    Single destination (not a fan-out list anymore).
    If the chat has a document, ALWAYS read it first — we need rag_context
    before we can know whether a URL inside the doc needs scraping.
    Chats without documents skip retrieval entirely.
    """
    if state["has_docs"]:
        return "rag_node"

    if state["has_urls"]:
        return "url_scrape_node"

    if state["needs_search"]:
        return "web_search_node"

    return "answer_node"


# ===========================
#  ROUTING EDGE — after rag_node
# ===========================
def route_after_rag(state: ChatState) -> str:
    """
    Now that we've read the document, check for URLs in BOTH the user's
    message and the retrieved document chunks. If found, scrape them.
    Otherwise fall back to web search or go straight to answering.
    """
    urls_in_msg = extract_urls(state["user_msg"])
    urls_in_doc = extract_urls(state.get("rag_context", ""))

    if state["has_urls"] or urls_in_msg or urls_in_doc:
        return "url_scrape_node"

    if state["needs_search"]:
        return "web_search_node"

    return "answer_node"


# ===========================
#  NODE 2A — RAG
# ===========================
def rag_node(state: ChatState) -> dict:
    """Return ONLY rag_context and sources.

    Retrieval itself lives in retrieval.py (hybrid + rerank by default).
    In the original "dense_mmr" mode it runs TWO passes and merges them:
      1. The user's actual query — for normal semantic relevance.
      2. A fixed "links / profile URLs" query — because a question like
         "how many questions have I solved on leetcode" is semantically
         about stats, not about the link sentence itself, so the chunk
         containing "leetcode.com/u/..." can miss the top-k cut on pass 1
         alone. This second pass guarantees URL-bearing chunks surface
         whenever the resume actually contains links.
    """
    _status("Reading your documents…")
    sources: list[dict] = []
    try:
        flt = scope_filter(state.get("user_id", "demo_user"), state["session_id"], state.get("file_id"),
                           project_id=state.get("project_id"))
        store = get_vectorstore()

        def search(query: str):
            return retrieve(query, flt, store=store, client=qdrant_client, collection=collection_name())

        docs = search(state["user_msg"])

        # The original dense pipeline needs a second pass to surface link
        # chunks (see docstring). Hybrid search matches "leetcode" etc. by
        # keyword, so it doesn't need — or pay for — the extra pass.
        link_docs = []
        if current_mode() == "dense_mmr":
            link_docs = search("LeetCode GitHub LinkedIn portfolio profile link URL website")

        # Merge, dedupe by page_content
        seen = set()
        merged = []
        for doc in docs + link_docs:
            if doc.page_content not in seen:
                seen.add(doc.page_content)
                merged.append(doc)

        # Number each passage so the answer can cite it as [n].
        blocks = []
        for number, doc in enumerate(merged, start=len(state.get("sources") or []) + 1):
            meta = doc.metadata or {}
            title = meta.get("file_name") or "Document"
            page = meta["page"] + 1 if isinstance(meta.get("page"), int) else None
            blocks.append(f"[{number}] ({title}{f', page {page}' if page else ''})\n{doc.page_content}")
            sources.append({"id": number, "type": "document", "title": title, "page": page,
                            "snippet": doc.page_content[:280]})
        context = "\n\n".join(blocks)
    except Exception as e:
        # Never feed the error text to the LLM as "document context" — it
        # would answer about the error instead of the user's question.
        logging.getLogger("aroma.agent.rag").warning("RAG retrieval failed: %s", e)
        context = ""

    if sources:
        _emit({"type": "sources", "sources": sources})
    return {"rag_context": context, "sources": sources}          # ← only own keys


# ===========================
#  NODE 2B — URL SCRAPE
# ===========================
def url_scrape_node(state: ChatState) -> dict:
    """
    Return ONLY search_context.
    Pulls URLs from the user's message AND from the document context
    (rag_context), since the link the user wants visited may have come
    from an uploaded PDF rather than being typed directly.
    """
    urls_msg = extract_urls(state["user_msg"])
    urls_doc = extract_urls(state.get("rag_context", ""))

    # Dedupe while preserving order, message URLs first
    seen = set()
    urls = []
    for u in urls_msg + urls_doc:
        if u not in seen:
            seen.add(u)
            urls.append(u)

    # Safety cap so a doc full of links doesn't trigger a scrape storm
    urls = urls[:5]

    parts = []
    sources: list[dict] = []
    agent = create_react_agent(llm, tools=[scrape_url])

    for url in urls:
        _status(f"Opening {_domain(url)}…")
        try:
            result = agent.invoke({
                "messages": [HumanMessage(content=f"""
Scrape the content at this URL: {url}

Report the most complete and accurate content you find. If the tool
says it could not extract meaningful content, say so plainly instead
of guessing or making up information.
""")]
            })
            content = result["messages"][-1].content
            parts.append(f"### Content from {url}:\n{content[:3000]}")
            sources.append({"id": len(state.get("sources") or []) + len(sources) + 1,
                            "type": "web", "title": _domain(url), "url": url})
        except Exception as e:
            parts.append(f"### Could not scrape {url}: {e}")

    if sources:
        _emit({"type": "sources", "sources": sources})
    return {"search_context": "\n\n".join(parts), "sources": sources}   # ← only own keys


# ===========================
#  NODE 2C — WEB SEARCH
# ===========================
def web_search_node(state: ChatState) -> dict:
    """Return ONLY search_context."""
    _status("Searching the web…")
    # Agent 1: search
    search_agent = create_react_agent(llm, tools=[web_search])
    search_result = search_agent.invoke({
        "messages": [HumanMessage(content=f"Find recent, reliable information about: {state['user_msg']}")]
    })
    search_output = search_result["messages"][-1].content

    start = len(state.get("sources") or []) + 1
    sources = [
        {"id": start + i, "type": "web", "title": title.strip() or _domain(url), "url": url}
        for i, (title, url) in enumerate(_parse_search_results(search_result["messages"])[:5])
    ]
    if sources:
        _emit({"type": "sources", "sources": sources})
        _status(f"Reading {len(sources)} results…")

    # Agent 2: read / optionally scrape
    reader_agent = create_react_agent(llm, tools=[scrape_url])
    reader_result = reader_agent.invoke({
        "messages": [HumanMessage(content=f"""
Original question: {state['user_msg']}

Web search snippets:
{search_output[:1500]}

If snippets fully answer the question, answer directly.
If not, call scrape_url on the most relevant URL, then answer.
Always end with a direct answer to the original question.
""")]
    })

    return {"search_context": reader_result["messages"][-1].content, "sources": sources}  # ← only own keys


# ===========================
#  NODE 3 — ANSWER
# ===========================
_mcp_logger = logging.getLogger("aroma.agent.mcp")


async def _load_mcp_tools(user_id: str) -> list:
    """Load the user's MCP tools; failures never break the chat request."""
    try:
        from mcp_client.manager import mcp_manager
        return await asyncio.wait_for(mcp_manager.load_tools(user_id), timeout=30)
    except Exception as exc:
        _mcp_logger.warning("MCP tool loading failed; continuing without MCP tools: %s", exc)
        return []


async def answer_node(state: ChatState) -> dict:
    """Merge all context, call LLM, persist to Redis. Return ONLY reply."""
    history = get_chat_history(state["session_id"])

    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in history:
        cls = HumanMessage if msg["role"] == "user" else AIMessage
        messages.append(cls(content=msg["content"]))

    # Assemble enriched prompt
    context_blocks = []
    if state.get("rag_context"):
        context_blocks.append(f"## Document Context:\n{state['rag_context']}")
    if state.get("search_context"):
        label = "## Scraped URL Content:" if (state["has_urls"] or state.get("rag_context")) else "## Web Search Results:"
        context_blocks.append(f"{label}\n{state['search_context']}")

    citation_rule = (
        " When you use a document passage, cite it inline with its number in square brackets, e.g. [1]."
        if state.get("rag_context") else ""
    )
    final_user_msg = (
        "\n\n".join(context_blocks)
        + f"\n\n## User Question:\n{state['user_msg']}"
        + "\n\nAnswer using the context above where relevant."
        + citation_rule
        if context_blocks
        else state["user_msg"]
    )

    messages.append(HumanMessage(content=final_user_msg))
    mcp_tools = await _load_mcp_tools(state.get("user_id", "demo_user"))
    _status("Writing the answer…")
    reply = ""
    if mcp_tools:
        # Existing web tools remain available together with dynamically
        # configured MCP tools, so the model can choose the right tool.
        # MCP adapter tools are async-only, so the agent must be awaited.
        agent = create_react_agent(llm, tools=[web_search, scrape_url, *mcp_tools])
        async for chunk, _meta in agent.astream({"messages": messages}, stream_mode="messages"):
            if isinstance(chunk, ToolMessage):
                # Text before a tool call is only a preamble; the answer comes after it.
                reply = ""
                _emit({"type": "reset"})
                continue
            if isinstance(chunk, AIMessageChunk):
                for call in chunk.tool_call_chunks or []:
                    if call.get("name"):
                        _status(f"Using {call['name']}…")
                text = _text(chunk.content)
                if text:
                    reply += text
                    _emit({"type": "token", "text": text})
    else:
        async for chunk in llm.astream(messages):
            text = _text(chunk.content)
            if text:
                reply += text
                _emit({"type": "token", "text": text})

    # Persist last 10 turns to Redis
    history.append({"role": "user", "content": state["user_msg"]})
    history.append({"role": "ai",   "content": reply})
    save_chat_history(state["session_id"], history[-10:])

    return {"reply": reply}              # ← only own key


# ===========================
#  BUILD THE GRAPH
# ===========================
def build_graph():
    g = StateGraph(ChatState)

    g.add_node("router_node",     router_node)
    g.add_node("rag_node",        rag_node)
    g.add_node("url_scrape_node", url_scrape_node)
    g.add_node("web_search_node", web_search_node)
    g.add_node("answer_node",     answer_node)

    g.set_entry_point("router_node")

    # router_node -> single next step (rag first if docs are involved)
    g.add_conditional_edges(
        "router_node",
        route_after_router,
        {
            "rag_node":        "rag_node",
            "url_scrape_node": "url_scrape_node",
            "web_search_node": "web_search_node",
            "answer_node":     "answer_node",
        },
    )

    # rag_node -> decide whether to scrape (URL found in doc or message),
    # search, or go straight to answering
    g.add_conditional_edges(
        "rag_node",
        route_after_rag,
        {
            "url_scrape_node": "url_scrape_node",
            "web_search_node": "web_search_node",
            "answer_node":     "answer_node",
        },
    )

    g.add_edge("url_scrape_node", "answer_node")
    g.add_edge("web_search_node", "answer_node")
    g.add_edge("answer_node",     END)

    return g.compile()


_graph = build_graph()


# ===========================
#  PUBLIC API
# ===========================
def _initial_state(user_msg: str, session_id: str, file_id: str | None, user_id: str,
                   project_id: str | None = None) -> dict:
    return {
        "user_msg":       user_msg,
        "session_id":     session_id,
        "file_id":        file_id,
        "user_id":        user_id,
        "project_id":     project_id,
        "has_urls":       False,
        "needs_search":   False,
        "has_docs":       False,
        "rag_context":    "",
        "search_context": "",
        "sources":        [],
        "reply":          "",
    }


def chat(user_msg: str, session_id: str, file_id: str = None, user_id: str = "demo_user") -> str:
    """Sync entry point for scripts (benchmarks). Async hosts should await achat()."""
    return asyncio.run(achat(user_msg, session_id, file_id, user_id))


async def achat(user_msg: str, session_id: str, file_id: str = None, user_id: str = "demo_user",
                project_id: str | None = None) -> str:
    try:
        result = await _graph.ainvoke(_initial_state(user_msg, session_id, file_id, user_id, project_id))
        return result["reply"]
    except Exception as e:
        print("GRAPH ERROR:", e)
        return "⚠️ AI service unavailable"


async def achat_stream(user_msg: str, session_id: str, file_id: str = None, user_id: str = "demo_user",
                       project_id: str | None = None):
    """Yield live events while the graph runs.

    Event types: status {label}, sources {sources}, token {text},
    reset (discard streamed text), then exactly one of
    done {response, sources} or error {message}.
    """
    final: dict = {}
    try:
        async for mode, chunk in _graph.astream(
            _initial_state(user_msg, session_id, file_id, user_id, project_id),
            stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                yield chunk
            else:
                final = chunk
        yield {"type": "done", "response": final.get("reply", ""), "sources": final.get("sources", [])}
    except Exception as e:
        print("GRAPH ERROR:", e)
        yield {"type": "error", "message": "⚠️ AI service unavailable"}
