<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,6&height=220&section=header&text=Aroma%20Multi-Agent%20Platform&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Production-Ready%20AI%20Multi-Agent%20Platform&descAlignY=58&descSize=20" />

<br/>

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

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=24&duration=3000&pause=1000&color=FF9800&center=true&vCenter=true&width=700&lines=Production+Ready+AI+Multi-Agent+Platform;FastAPI+%2B+OpenAI+%2B+Redis;RAG+Powered+Knowledge+Retrieval;Voice+AI+%2B+Vector+Search;Built+for+Scalable+AI+Applications" />

</div>

---

# 🧠 Aroma Multi-Agent Platform

**Aroma Multi-Agent Platform** is a production-ready AI platform that combines multiple intelligent agents into a single application. It supports conversational AI, Retrieval-Augmented Generation (RAG), semantic vector search, voice interaction, Redis caching, and external tool integrations.

The project is designed with a modular architecture, making it easy to extend with new AI agents and tools.

---

# ✨ Features

* 🤖 Multi-Agent AI Architecture
* 💬 GPT-powered Conversational Assistant
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
C[OpenAI]
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
* OpenAI API
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
OPENAI_API_KEY=

DEEPGRAM_API_KEY=

DATABASE_URL=

REDIS_URL=

QDRANT_URL=
```

---

# 📈 Roadmap

* ✅ Multi-Agent Architecture
* ✅ GPT Chat
* ✅ Voice Assistant
* ✅ PDF Chat
* ✅ RAG Pipeline
* ✅ Redis Cache
* ⏳ Multi-Document Memory
* ⏳ Authentication
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