<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,6&height=220&section=header&text=Aroma%20Multi-Agent%20Platform&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Production-Ready%20AI%20Multi-Agent%20Platform&descAlignY=58&descSize=20" />

<br/>

<a href="https://github.com/shivamkr082003/aroma-multiagent-platform/actions/workflows/ci.yml">
  <img src="https://img.shields.io/github/actions/workflow/status/shivamkr082003/aroma-multiagent-platform/ci.yml?branch=main&style=for-the-badge&label=CI&labelColor=1a1a1a" />
</a>

<a href="https://github.com/shivamkr082003/aroma-multiagent-platform/stargazers">
  <img src="https://img.shields.io/github/stars/shivamkr082003/aroma-multiagent-platform?style=for-the-badge&color=ff9800&labelColor=1a1a1a" />
</a>

<a href="https://github.com/shivamkr082003/aroma-multiagent-platform/network/members">
  <img src="https://img.shields.io/github/forks/shivamkr082003/aroma-multiagent-platform?style=for-the-badge&color=4caf50&labelColor=1a1a1a" />
</a>

<a href="https://github.com/shivamkr082003/aroma-multiagent-platform/issues">
  <img src="https://img.shields.io/github/issues/shivamkr082003/aroma-multiagent-platform?style=for-the-badge&color=2196f3&labelColor=1a1a1a" />
</a>


<br/><br/>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=24&duration=3000&pause=1000&color=FF9800&center=true&vCenter=true&width=700&lines=Production+Ready+AI+Multi-Agent+Platform;FastAPI+%2B+xAI+Grok+%2B+Redis;RAG+Powered+Knowledge+Retrieval;Voice+AI+%2B+Vector+Search;Built+for+Scalable+AI+Applications" />

</div>

---

# 🧠 Aroma Multi-Agent Platform

**Aroma Multi-Agent Platform** is a production-ready AI platform that combines multiple intelligent agents into a single application. It supports conversational AI, Retrieval-Augmented Generation (RAG), semantic vector search, voice interaction, Redis caching, and external tool integrations.

The project is designed with a modular architecture, making it easy to extend with new AI agents and tools.

---

# ✨ Features

* 🤖 Multi-Agent AI Architecture
* 💬 Grok-powered Conversational Assistant
* 📄 PDF Chat using Retrieval-Augmented Generation (RAG)
* 🔍 Semantic Search with Qdrant
* 🎤 Voice Interaction using Deepgram
* ⚡ Redis Caching
* 🗄️ PostgreSQL Database
* 🛠️ External API Integrations
* 🐳 Docker Support
* 🚀 FastAPI Backend
* 🔒 Scalable & Production Ready

---

# 🖼️ Preview

<div align="center">

<img src="./assets/aroma-ai-preview.png" width="90%" />

</div>

---

# 🏗️ System Architecture

```mermaid
flowchart TD

A[AI Multi-Agent Platform]

subgraph Chat
B[Chat Agent]
C[xAI Grok]
D[(Postgres)]
E[(Redis)]
B --> C
C --> D
C --> E
end

subgraph RAG
F[PDF Upload]
G[(Qdrant)]
F --> G
end

subgraph Voice
H[Voice Agent]
I[Deepgram]
H --> I
end

subgraph Tools
J[External Tools]
K[Third Party APIs]
J --> K
end

A --> B
A --> F
A --> H
A --> J
```

---

# 🛠️ Tech Stack

* Python
* FastAPI
* TypeScript
* PostgreSQL
* Redis
* Qdrant
* Docker
* xAI Grok API
* Deepgram API

---

# 📂 Project Structure

```text
aroma-multiagent-platform/

├── Agent/
├── alembic/
├── crud/
├── docker/
├── frontend/
├── models/
├── create_tables.py
├── db.py
├── main.py
├── redis_client.py
├── requirements.txt
└── README.md
```

---

# 🚀 Getting Started

## Clone Repository

```bash
git clone https://github.com/shivamkr082003/aroma-multiagent-platform.git

cd aroma-multiagent-platform
```

---

## Backend Setup

```bash
python -m venv venv

source venv/bin/activate

pip install -r requirements.txt

python create_tables.py

uvicorn main:app --reload
```

---

## Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

## Docker

```bash
cd docker

docker-compose up --build
```

---

# ⚙️ Environment Variables

```env
XAI_API_KEY=

DEEPGRAM_API_KEY=

DATABASE_URL=

REDIS_URL=

QDRANT_URL=
```

---

# 🔐 Authentication

Email/password accounts with a signed session in an **httpOnly cookie** (JavaScript can't read it). Every chat, upload, voice and MCP endpoint is scoped to the signed-in user.

* Passwords are hashed with **scrypt** (Python stdlib), never stored in plain text.
* Sessions are **JWTs** signed with `AUTH_SECRET_KEY`, valid for 7 days by default.
* After 5 wrong passwords, an email is locked for 15 minutes (counters in Redis).
* Users can't read or write each other's chats, documents or MCP servers.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # put in AUTH_SECRET_KEY
alembic upgrade head                                            # creates the users table
```

Open the frontend at `http://localhost:3000` (it calls the API on the same hostname, port 8000).
When the frontend and API are on different domains in production, set `NEXT_PUBLIC_API_URL`, `AUTH_COOKIE_SECURE=true` and `AUTH_COOKIE_SAMESITE=none`.

---

# 🔎 Retrieval & Evaluation

Document chat uses **hybrid search + reranking** ([retrieval.py](retrieval.py)):
dense vectors (BGE-small, local) find passages by meaning, **BM25** finds exact
names, numbers and codes, **Reciprocal Rank Fusion** merges both lists, and a
**cross-encoder** reranks the top 20. Answers cite passages inline as `[1]`.

Measured with `python -m evaluation.run_eval` on 40 labelled questions over 4 documents
(19 exact-fact, 21 paraphrased), top-5 retrieval:

| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | MRR (exact) | MRR (paraphrased) | p50 latency |
|---|---|---|---|---|---|---|---|
| Dense + MMR (original) | 0.650 | 0.725 | 0.800 | 0.695 | 0.768 | 0.630 | 12 ms |
| Dense | 0.650 | 0.875 | 0.950 | 0.767 | 0.842 | 0.700 | 6 ms |
| Hybrid (dense + BM25) | 0.650 | 1.000 | 1.000 | 0.821 | 0.868 | 0.778 | 8 ms |
| **Hybrid + rerank** (default) | **0.825** | **1.000** | **1.000** | **0.904** | **0.947** | **0.865** | 123 ms |

`--answers` adds LLM-judged **correctness** and **faithfulness** (RAGAS-style) using Groq.
Results are saved to `benchmark-results/retrieval-eval.json`. Switch modes with `RETRIEVAL_MODE`.

---

# 🔌 MCP Servers

Aroma can use tools from your own [MCP](https://modelcontextprotocol.io) servers during chat. Add them from **MCP Servers** in the sidebar, or via the API (`/mcp/servers`).

* **HTTP / SSE** servers work out of the box.
* **STDIO** servers run a local process on the backend host, so they are **off by default**. Enable them only on a backend that you alone use:

```env
MCP_ALLOW_STDIO=true
MCP_STDIO_ALLOWED_COMMANDS=npx,uvx   # bare command names only
```

* Server `headers` / `env` (API keys) are encrypted at rest and always masked in API responses. Set a key before storing them:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# put the output in MCP_SECRET_KEY; losing it makes stored secrets unreadable
```

Run the tests with `pytest`.

---

# 📈 Roadmap

* ✅ Multi-Agent Architecture
* ✅ Grok Chat
* ✅ Voice Assistant
* ✅ PDF Chat
* ✅ RAG Pipeline
* ✅ Redis Cache
* ✅ MCP Tool Servers
* ✅ Multi-Document Projects (shared documents across chats)
* ✅ Prompt Templates & Usage Statistics
* ✅ Authentication
* ⏳ Team Collaboration
* ⏳ Cloud Deployment

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository.
2. Create your feature branch.
3. Commit your changes.
4. Push your branch.
5. Open a Pull Request.


---

<div align="center">

## ⭐ Star this repository if you found it useful!

### Developed by **Shivam Kumar**

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,6&height=120&section=footer"/>

</div>