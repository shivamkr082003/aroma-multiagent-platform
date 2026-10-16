<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,6&height=200&section=header&text=Aroma%20AI&fontSize=64&fontColor=ffffff&animation=fadeIn&fontAlignY=36&desc=Multi-agent%20assistant%20for%20your%20documents%2C%20voice%2C%20the%20web%20and%20your%20tools&descAlignY=58&descSize=17" />

<a href="https://github.com/shivamkr082003/aroma-multiagent-platform/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/shivamkr082003/aroma-multiagent-platform/ci.yml?branch=main&style=for-the-badge&label=CI&labelColor=1a1a1a" /></a> <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white&labelColor=1a1a1a" /> <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white&labelColor=1a1a1a" /> <img src="https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=nextdotjs&logoColor=white&labelColor=1a1a1a" /> <img src="https://img.shields.io/badge/LangGraph-agents-f97316?style=for-the-badge&labelColor=1a1a1a" />

<br/><br/>

<b>
<a href="#-demo">Demo</a> ·
<a href="#-feature-tour">Feature tour</a> ·
<a href="#%EF%B8%8F-architecture">Architecture</a> ·
<a href="#-retrieval-quality">Evaluation</a> ·
<a href="#-getting-started">Getting started</a> ·
<a href="#-api-reference">API</a>
</b>

</div>

---

## 🎬 Demo

<div align="center">

<img src="docs/demo/aroma-demo.gif" alt="Aroma AI demo: signing in, asking a question inside a project, live agent status, a streamed answer with citations, statistics and MCP tools" width="92%" />

<sub>Sign in → ask a question inside a project → watch the agent work → answer with clickable citations → statistics → MCP tools.<br/>
<b><a href="docs/demo/aroma-demo.mp4">▶ Full-quality video (MP4, 43 s)</a></b></sub>

</div>

---

## 💡 What is Aroma?

**Aroma** is a full-stack AI assistant built around a **LangGraph multi-agent pipeline**. For every message it decides what the question needs — your documents, a live web search, a link to read, or one of your own tools — gathers that context, and **streams** an answer that **cites its sources** passage by passage.

<table>
<tr>
<td align="center" width="25%"><h3>0.695 → 0.904</h3><sub>retrieval MRR on our<br/>40-question benchmark</sub></td>
<td align="center" width="25%"><h3>80% → 100%</h3><sub>right passage in the top 5<br/>(same benchmark)</sub></td>
<td align="center" width="25%"><h3>75</h3><sub>automated tests<br/>on every push</sub></td>
<td align="center" width="25%"><h3>27</h3><sub>documented<br/>API endpoints</sub></td>
</tr>
</table>

**Highlights**

- 🧠 **Agentic routing** — a LangGraph router sends each question to document search, web search, link scraping or straight to the LLM.
- 🔎 **Hybrid retrieval** — semantic vectors + BM25 keywords, fused with Reciprocal Rank Fusion and re-scored by a cross-encoder. Measured, not guessed ([results](#-retrieval-quality)).
- 📌 **Citations** — every document answer links `[1]`, `[2]` … to the exact passage and page.
- ⚡ **Live streaming** — the answer types itself out, and Aroma shows what it is doing (*Reading your documents…*, *Searching the web…*).
- 📁 **Projects** — a NotebookLM-style workspace: add documents once, ask across all of them from any chat in the project.
- 🎤 **Voice** — speak a question, get a spoken answer (Deepgram speech-to-text and text-to-speech).
- 🔌 **MCP tools** — connect any Model Context Protocol server; the agent calls its tools when they help.
- 🔐 **Real accounts** — email/password and Google sign-in, httpOnly sessions, per-user data isolation, encrypted secrets.

---

## 📸 Feature tour

<table>
<tr>
<td width="50%"><b>Answers with citations</b><br/><sub>Click a badge to open the exact passage it came from.</sub><br/><img src="docs/screenshots/04-chat-citations.png" alt="Chat answer with numbered citations and an opened source passage" /></td>
<td width="50%"><b>Web search with sources</b><br/><sub>Fresh questions are answered from the web, with links.</sub><br/><img src="docs/screenshots/05-chat-web-search.png" alt="Answer built from a web search, listing five web sources" /></td>
</tr>
<tr>
<td><b>Projects</b><br/><sub>Documents shared by every chat in the project.</sub><br/><img src="docs/screenshots/08-project-detail.png" alt="Project page with documents and chats" /></td>
<td><b>Statistics</b><br/><sub>Activity, response time and where answers came from.</sub><br/><img src="docs/screenshots/10-statistics.png" alt="Statistics dashboard" /></td>
</tr>
</table>

<details>
<summary><b>More screenshots</b> — live status, MCP tools, templates, sign-in, mobile and more</summary>
<br/>

<table>
<tr>
<td width="50%"><b>Live agent status</b><br/><img src="docs/screenshots/06-live-status.png" alt="Live status shown while the agent works" /></td>
<td width="50%"><b>MCP servers</b><br/><img src="docs/screenshots/11-mcp-servers.png" alt="MCP servers panel with a connected server and its tools" /></td>
</tr>
<tr>
<td><b>Prompt templates</b><br/><img src="docs/screenshots/09-templates.png" alt="Templates page" /></td>
<td><b>All projects</b><br/><img src="docs/screenshots/07-projects.png" alt="Projects overview" /></td>
</tr>
<tr>
<td><b>Sign in (email or Google)</b><br/><img src="docs/screenshots/01-login.png" alt="Login page" /></td>
<td><b>Create account</b><br/><img src="docs/screenshots/02-register.png" alt="Register page" /></td>
</tr>
<tr>
<td><b>New chat</b><br/><img src="docs/screenshots/03-chat-home.png" alt="Empty chat with suggestions" /></td>
<td><b>Updates & FAQ</b><br/><img src="docs/screenshots/12-updates-faq.png" alt="Updates and FAQ page" /></td>
</tr>
<tr>
<td align="center"><b>Mobile sign-in</b><br/><img src="docs/screenshots/14-mobile-login.png" alt="Mobile sign-in" width="60%" /></td>
<td align="center"><b>Mobile chat</b><br/><img src="docs/screenshots/13-mobile-chat.png" alt="Mobile chat" width="60%" /></td>
</tr>
</table>

</details>

---

## 🏗️ Architecture

### System overview

```mermaid
flowchart LR
    U(["👤 User<br/>browser · microphone"])

    subgraph FE["Frontend · Next.js 16 + Tailwind"]
        UI["Chat · Projects · Templates<br/>Statistics · MCP panel"]
    end

    subgraph BE["Backend · FastAPI"]
        API["REST + SSE API<br/>auth · chat · upload · voice"]
        AG["LangGraph agent"]
        RET["Hybrid retrieval<br/>dense + BM25 + rerank"]
        MC["MCP client"]
    end

    subgraph DATA["Storage"]
        PG[("PostgreSQL<br/>users · chats · projects")]
        QD[("Qdrant<br/>document vectors")]
        RD[("Redis<br/>chat memory · rate limits")]
    end

    subgraph EXT["External services"]
        LLM["Groq LLM<br/>gpt-oss-120b"]
        WEB["Tavily<br/>web search"]
        DG["Deepgram<br/>speech ↔ text"]
        MS["Your MCP servers"]
        GG["Google Sign-In"]
    end

    U --> UI --> API
    API --> AG
    AG --> RET --> QD
    AG --> LLM
    AG --> WEB
    AG --> MC --> MS
    AG --> RD
    API --> PG
    API --> DG
    UI -. "ID token" .-> GG
```

### The agent: how a question is routed

```mermaid
flowchart TD
    Q(["User message"]) --> R{"router_node<br/>what does it need?"}
    R -- "chat or project has documents" --> RAG["rag_node<br/>hybrid search + rerank"]
    R -- "message contains a link" --> SC["url_scrape_node<br/>read the page"]
    R -- "needs fresh information" --> WS["web_search_node<br/>Tavily"]
    R -- "general question" --> ANS
    RAG -- "a link inside the document" --> SC
    RAG -- "needs fresh information" --> WS
    RAG --> ANS
    SC --> ANS
    WS --> ANS
    ANS["answer_node<br/>Groq LLM + your MCP tools"] --> OUT(["Streamed answer<br/>with numbered sources"])
```

Each node emits live events (`status`, `sources`, `token`) through LangGraph's stream writer, so the UI can show progress before the answer starts.

### Life of a chat request

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as FastAPI
    participant G as LangGraph agent
    participant Q as Qdrant
    participant L as Groq LLM
    B->>A: POST /chat/stream (session cookie)
    A->>A: verify session · check the chat belongs to this user
    A->>G: run the graph (astream)
    G-->>B: status "Understanding your question…"
    G->>Q: hybrid search, scoped to this user's chat + project
    G-->>B: sources [1] … [n]
    G->>L: question + numbered passages
    L-->>G: tokens
    G-->>B: token · token · token …
    G-->>B: done (full answer + sources)
    A->>A: save the answer and its sources (PostgreSQL)
```

### Retrieval pipeline

```mermaid
flowchart LR
    Q["Question"] --> D["Dense search<br/>BGE-small embeddings<br/>top 20"]
    Q --> K["BM25 keyword search<br/>top 20"]
    D --> F["Reciprocal Rank Fusion"]
    K --> F
    F --> X["Cross-encoder rerank<br/>MiniLM-L6"]
    X --> T["Top 5 passages<br/>numbered for citation"]
```

Embeddings and the reranker run **locally on the CPU** — no paid embedding API is needed.

---

## 📊 Retrieval quality

Measured with `python -m evaluation.run_eval` on **40 labelled questions** over 4 documents (19 exact-fact, 21 paraphrased). A hit means the retrieved passage contains the labelled answer.

| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | MRR (exact) | MRR (paraphrased) | p50 latency |
|---|---|---|---|---|---|---|---|
| Dense + MMR (original) | 0.650 | 0.725 | 0.800 | 0.695 | 0.768 | 0.630 | 12 ms |
| Dense | 0.650 | 0.875 | 0.950 | 0.767 | 0.842 | 0.700 | 6 ms |
| Hybrid (dense + BM25) | 0.650 | 1.000 | 1.000 | 0.821 | 0.868 | 0.778 | 8 ms |
| **Hybrid + rerank** (default) | **0.825** | **1.000** | **1.000** | **0.904** | **0.947** | **0.865** | 123 ms |

- **Exact facts** (names, IDs, numbers) gain the most from BM25; **paraphrased** questions gain the most from the reranker.
- `--answers` adds LLM-judged **correctness** and **faithfulness** (RAGAS-style).
- Raw results: [`benchmark-results/retrieval-eval.json`](benchmark-results/retrieval-eval.json). The corpus is a small controlled benchmark — add your own documents to `evaluation/corpus/` and questions to `evaluation/questions.json`.

---

## 🛠️ Tech stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4 |
| **Backend** | FastAPI, Server-Sent Events, SQLAlchemy, Alembic |
| **Agents** | LangGraph, LangChain, Groq (`gpt-oss-120b`) |
| **Retrieval** | Qdrant, BGE-small embeddings, BM25 (`rank-bm25`), cross-encoder reranker (sentence-transformers) |
| **Data** | PostgreSQL (Neon), Redis (chat memory, rate limits), Qdrant (vectors) |
| **Voice** | Deepgram Nova-2 (speech-to-text), Aura (text-to-speech), ffmpeg |
| **Tools** | Model Context Protocol (`langchain-mcp-adapters`), Tavily web search, Playwright scraping |
| **Auth** | scrypt password hashing, JWT in httpOnly cookies, Google Identity Services |
| **Quality** | pytest (75 tests), ESLint, TypeScript, GitHub Actions CI, Docker |

---

## 📂 Project structure

```text
aroma-multiagent-platform/
├── Agent/agent.py          # LangGraph graph: router → rag / scrape / web search → answer (streaming)
├── retrieval.py            # dense, BM25, Reciprocal Rank Fusion, cross-encoder rerank
├── rag_store.py            # embedding model, Qdrant collection, chunking
├── documents.py            # upload pipeline: extract → chunk → embed; list / delete documents
├── main.py                 # FastAPI app: chat (+SSE stream), upload, voice
├── auth/                   # register / login / Google sign-in, JWT cookies, rate limiting
├── routers/                # projects, templates, statistics, chat management
├── mcp_client/             # MCP server registry, encryption of secrets, tool loading
├── models/ · crud/         # SQLAlchemy models and data access
├── alembic/                # database migrations
├── evaluation/             # retrieval benchmark: corpus, labelled questions, harness
├── tests/                  # 75 pytest tests (in-memory SQLite + Qdrant, mocked APIs)
├── frontend/               # Next.js app: chat, auth pages, projects, templates, stats, MCP
├── dev.py                  # one command to run backend + frontend locally
├── Dockerfile              # single container: API + static frontend
└── deploy/deploy_hf.py     # one-command deploy to a Hugging Face Space
```

---

## 🚀 Getting started

### Prerequisites

Python 3.12+, Node.js 20+, Docker (for local Qdrant / Redis / Postgres) and ffmpeg (voice).

### 1. Install

```bash
git clone https://github.com/shivamkr082003/aroma-multiagent-platform.git
cd aroma-multiagent-platform

# Qdrant, Redis and Postgres
cd docker && docker compose up -d && cd ..

# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then fill in your keys (see below)

# Frontend
cd frontend && npm install && cd ..
```

### 2. Run

```bash
python dev.py
```

One command: runs database migrations, starts the API and the web app on **free ports** (if 8000/3000 are busy it picks the next ones and wires the frontend to the right API), and prints the URL to open. Running it again restarts Aroma instead of failing with "address already in use". **Ctrl+C** stops everything.

### 3. Configure (`.env`)

| Variable | Needed for | Notes |
|---|---|---|
| `GROQ_API_KEY` | everything | [console.groq.com](https://console.groq.com) |
| `DATABASE_URL` | everything | PostgreSQL URL (local Docker or [Neon](https://neon.tech)) |
| `AUTH_SECRET_KEY` | sign-in | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `TAVILY_API_KEY` | web search | [tavily.com](https://tavily.com) |
| `DEEPGRAM_API_KEY` | voice | [deepgram.com](https://deepgram.com) |
| `REDIS_URL` | chat memory | default `redis://localhost:6379/0` |
| `QDRANT_URL` / `QDRANT_API_KEY` | documents | key only for Qdrant Cloud |
| `MCP_SECRET_KEY` | MCP API keys | Fernet key; encrypts MCP headers at rest |
| `GOOGLE_CLIENT_ID` | Google sign-in | optional; OAuth *Web* client ID, no secret needed |

<details>
<summary><b>Optional settings</b></summary>

| Variable | Default | Purpose |
|---|---|---|
| `RETRIEVAL_MODE` | `hybrid_rerank` | `dense_mmr` · `dense` · `hybrid` · `hybrid_rerank` |
| `EMBEDDING_PROVIDER` | `local` | `local` (free, CPU) or `openai` |
| `LOCAL_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | any sentence-transformers model |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | cross-encoder for reranking |
| `MCP_ALLOW_STDIO` | `false` | allow MCP servers that run a local command |
| `MCP_STDIO_ALLOWED_COMMANDS` | — | allowlist, e.g. `npx,uvx` |
| `AUTH_TOKEN_TTL_HOURS` | `168` | session length |
| `AUTH_COOKIE_SECURE` / `AUTH_COOKIE_SAMESITE` | `false` / `lax` | use `true` / `none` when frontend and API are on different sites |
| `DB_PREFER_IPV4` | `true` | avoids slow or broken IPv6 routes to the database |

</details>

<details>
<summary><b>Setting up Google sign-in</b></summary>

1. [Google Cloud Console](https://console.cloud.google.com) → new project → **Google Auth Platform** → *Get started* (External).
2. **Clients → Create client → Web application**. Under *Authorized JavaScript origins* add `http://localhost`, `http://localhost:3000`, `http://localhost:3001` (and your production URL). No redirect URI or client secret is needed.
3. Put the client ID in `.env` as `GOOGLE_CLIENT_ID`. While the app is in *Testing*, add your account under **Audience → Test users**.

</details>

---

## 🔌 API reference

Interactive docs at **`/docs`** (Swagger) when the API is running.

| Area | Endpoints |
|---|---|
| **Auth** | `POST /auth/register` · `POST /auth/login` · `POST /auth/google` · `POST /auth/logout` · `GET /auth/me` · `GET /auth/config` |
| **Chat** | `POST /chat/stream` (SSE: `status`, `sources`, `token`, `done`) · `POST /chat` · `POST /upload` · `POST /voice` |
| **Chats** | `GET /sessions` · `GET /messages/{id}` · `PATCH /sessions/{id}` · `DELETE /sessions/{id}` · `DELETE /sessions` |
| **Projects** | `GET·POST /projects` · `GET·PATCH·DELETE /projects/{id}` · `GET·POST /projects/{id}/documents` · `DELETE /projects/{id}/documents/{file_id}` |
| **Templates** | `GET·POST /templates` · `DELETE /templates/{id}` |
| **Statistics** | `GET /stats` |
| **MCP** | `GET·POST /mcp/servers` · `GET·PUT·DELETE /mcp/servers/{id}` · `POST …/enable` · `POST …/disable` · `POST …/test` · `GET /mcp/config` |
| **Health** | `GET /health` |

---

## 🔐 Security

- **Passwords** hashed with scrypt; **sessions** are signed JWTs in httpOnly cookies (not readable by JavaScript).
- **Brute-force protection** — 5 failed logins lock an email for 15 minutes (Redis counters).
- **Data isolation** — every chat, document, project, template and MCP server is scoped to its owner and checked on every request (covered by tests).
- **Google sign-in** verifies the ID token's signature, audience, issuer, expiry and verified email. Linking a Google account drops any unverified password set on that email, so an account can't be pre-registered and hijacked.
- **MCP secrets** (API keys in headers/env) are encrypted at rest and never returned by the API; local-command MCP servers are off unless explicitly allowed.
- **No secrets in git** — configuration comes from the environment only.

---

## 🧪 Testing & CI

```bash
pytest                    # 75 tests: auth, streaming, retrieval, projects, MCP, voice
cd frontend && npm run lint && npx tsc --noEmit
```

Tests run against in-memory SQLite and Qdrant with every external API mocked, so they need no keys or services. **GitHub Actions** runs the backend tests and the frontend type-check, lint and production build on every push.

---

## ☁️ Deployment

The `Dockerfile` builds **one container**: the FastAPI backend serves the statically exported frontend on the same origin (one URL, first-party cookies, no CORS). Migrations run automatically on start.

```bash
docker build -t aroma-ai .
docker run -p 7860:7860 --env-file .env aroma-ai
```

The container needs about **2 GB of RAM** (local embedding model + reranker). `python deploy/deploy_hf.py` deploys it to a Hugging Face Space in one command (Docker Spaces require a PRO plan); any Docker host with 2 GB+ works — a VM, Google Cloud Run, Railway or a DigitalOcean droplet.

---

## 🗺️ Roadmap

- [x] Multi-agent routing with LangGraph
- [x] Hybrid retrieval + reranking, with an evaluation harness
- [x] Streaming answers with live status and citations
- [x] Projects, templates, statistics
- [x] Voice assistant
- [x] MCP tool servers
- [x] Accounts: email/password + Google
- [x] CI and Docker
- [ ] Public deployment
- [ ] Team workspaces and sharing
- [ ] Hands-free voice mode (streaming speech)

---

## 🤝 Contributing

Contributions are welcome: fork the repository, create a feature branch, make sure `pytest` and `npm run lint` pass, and open a pull request.

---

<div align="center">

### Built by **Shivam Kumar**

<sub>If Aroma helped you, consider giving the repository a ⭐</sub>

</div>
