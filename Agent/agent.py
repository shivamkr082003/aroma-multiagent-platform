from dotenv import load_dotenv
load_dotenv()

import re
import json
import operator
from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from redis_client import get_chat_history, save_chat_history
from tools import web_search, scrape_url

# ===========================
#  SETUP
# ===========================
qdrant_client = QdrantClient(url="http://localhost:6333")

llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.7, timeout=60, max_retries=2)
router_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

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
#     ├── has_docs/session  -> rag_node -> route_after_rag -> {url_scrape_node | web_search_node | answer_node}
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

    # ── Routing flags (written only by router_node) ──
    has_urls:     bool
    needs_search: bool
    has_docs:     bool

    # ── Accumulators ──
    #    operator.add on str  →  concatenation
    rag_context:    Annotated[str, operator.add]
    search_context: Annotated[str, operator.add]

    # ── Final output (written only by answer_node) ──
    reply: str


# ===========================
#  NODE 1 — ROUTER
# ===========================
def router_node(state: ChatState) -> dict:
    """Classify the message; return ONLY the keys this node owns."""
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
        "has_docs":     flags.get("has_docs",     False) or bool(state.get("file_id")),
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
    If docs are involved, ALWAYS go read them first — we need rag_context
    before we can know whether a URL inside the doc needs scraping.
    """
    if state["has_docs"] or state["session_id"]:
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
    """Return ONLY rag_context.

    Runs TWO retrieval passes and merges them:
      1. The user's actual query — for normal semantic relevance.
      2. A fixed "links / profile URLs" query — because a question like
         "how many questions have I solved on leetcode" is semantically
         about stats, not about the link sentence itself, so the chunk
         containing "leetcode.com/u/..." can miss the top-k cut on pass 1
         alone. This second pass guarantees URL-bearing chunks surface
         whenever the resume actually contains links.
    """
    try:
        vectorstore = QdrantVectorStore(
            client=qdrant_client,
            collection_name="docs",
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
        )

        filter_condition = (
            {"must": [{"key": "metadata.file_id",   "match": {"value": state["file_id"]}}]}
            if state.get("file_id")
            else
            {"must": [{"key": "metadata.session_id", "match": {"value": state["session_id"]}}]}
        )

        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10, "lambda_mult": 0.5, "filter": filter_condition},
        )

        docs = retriever.invoke(state["user_msg"])

        # Second pass: explicitly fish for link/profile chunks
        link_query = "LeetCode GitHub LinkedIn portfolio profile link URL website"
        link_docs = retriever.invoke(link_query)

        # Merge, dedupe by page_content
        seen = set()
        merged = []
        for doc in docs + link_docs:
            if doc.page_content not in seen:
                seen.add(doc.page_content)
                merged.append(doc.page_content)

        context = "\n\n".join(merged)
    except Exception as e:
        context = f"[RAG error: {e}]"

    return {"rag_context": context}          # ← only own key


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
    agent = create_react_agent(llm, tools=[scrape_url])

    for url in urls:
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
        except Exception as e:
            parts.append(f"### Could not scrape {url}: {e}")

    return {"search_context": "\n\n".join(parts)}   # ← only own key


# ===========================
#  NODE 2C — WEB SEARCH
# ===========================
def web_search_node(state: ChatState) -> dict:
    """Return ONLY search_context."""
    # Agent 1: search
    search_agent = create_react_agent(llm, tools=[web_search])
    search_result = search_agent.invoke({
        "messages": [HumanMessage(content=f"Find recent, reliable information about: {state['user_msg']}")]
    })
    search_output = search_result["messages"][-1].content

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

    return {"search_context": reader_result["messages"][-1].content}  # ← only own key


# ===========================
#  NODE 3 — ANSWER
# ===========================
def answer_node(state: ChatState) -> dict:
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

    final_user_msg = (
        "\n\n".join(context_blocks)
        + f"\n\n## User Question:\n{state['user_msg']}"
        + "\n\nAnswer using the context above where relevant."
        if context_blocks
        else state["user_msg"]
    )

    messages.append(HumanMessage(content=final_user_msg))
    reply = llm.invoke(messages).content

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
def chat(user_msg: str, session_id: str, file_id: str = None) -> str:
    try:
        result = _graph.invoke({
            "user_msg":       user_msg,
            "session_id":     session_id,
            "file_id":        file_id,
            "has_urls":       False,
            "needs_search":   False,
            "has_docs":       False,
            "rag_context":    "",
            "search_context": "",
            "reply":          "",
        })
        return result["reply"]
    except Exception as e:
        print("GRAPH ERROR:", e)
        return "⚠️ AI service unavailable"