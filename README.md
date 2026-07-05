
<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,6&height=220&section=header&text=Aroma%20AI&fontSize=70&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Your%20Intelligent%20Multi-Modal%20AI%20Assistant&descAlignY=58&descSize=20" />

<br/>

<a href="https://github.com/Rohan77ux/Aroma-Ai/stargazers">
  <img src="https://img.shields.io/github/stars/Rohan77ux/Aroma-Ai?style=for-the-badge&color=ff9800&labelColor=1a1a1a" />
</a>
<a href="https://github.com/Rohan77ux/Aroma-Ai/network/members">
  <img src="https://img.shields.io/github/forks/Rohan77ux/Aroma-Ai?style=for-the-badge&color=4caf50&labelColor=1a1a1a" />
</a>
<a href="https://github.com/Rohan77ux/Aroma-Ai/issues">
  <img src="https://img.shields.io/github/issues/Rohan77ux/Aroma-Ai?style=for-the-badge&color=2196f3&labelColor=1a1a1a" />
</a>
<a href="https://github.com/Rohan77ux/Aroma-Ai/blob/main/LICENSE">
  <img src="https://img.shields.io/badge/license-MIT-9c27b0?style=for-the-badge&labelColor=1a1a1a" />
</a>

<br/><br/>

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=24&duration=3000&pause=1000&color=FF9800&center=true&vCenter=true&width=600&lines=Ask+Questions+%26+Get+Instant+Answers;Talk+to+Aroma+with+Your+Voice+%F0%9F%8E%A4;Upload+a+PDF+and+Chat+With+It+%F0%9F%93%84;Powered+by+RAG+%2B+Vector+Search+%E2%9A%A1" alt="Typing SVG" />

</div>

<br/>

## 🧠 What is Aroma AI?

**Aroma AI** is a GPT-style intelligent assistant that goes beyond plain text chat. It can answer your questions, **listen and respond to your voice**, and let you **upload a PDF to ask questions directly about its content** — powered by a Retrieval-Augmented Generation (RAG) pipeline under the hood.

<br/>

<div align="center">

| 💬 Smart Chat | 🎤 Voice AI | 📄 PDF Q&A | ⚡ Fast Caching |
|:---:|:---:|:---:|:---:|
| Natural conversations using the OpenAI API | Speak and get spoken responses via Deepgram | Upload PDFs and query them instantly | Redis-powered caching for snappy replies |

</div>

<br/>

## ✨ Features

- 🤖 **Conversational AI** — Ask anything and get accurate, GPT-powered answers
- 🎤 **Voice Interaction** — Speak your queries and get natural voice responses (Deepgram)
- 📄 **PDF Question Answering** — Upload documents and chat with their content using RAG
- 📚 **Vector Search** — Semantic document retrieval powered by Qdrant
- 🛠️ **Tool Integrations** — Connects with third-party APIs to extend capabilities
- ⚡ **Optimized Performance** — Redis caching and a robust Postgres backend

<br/>

## 🖼️ Preview

<div align="center">
  <img src="./assets/aroma-ai-preview.png" alt="Aroma AI chat interface" width="90%" />
</div>

<br/>

## 🏗️ System Architecture

```mermaid
flowchart TD
    A[🧠 Aroma AI Core]

    subgraph CHAT["💬 Chat Engine"]
        D[Normal Chat]
        E[OpenAI API]
        F[(Postgres)]
        G[(Redis Cache)]
        D --> E --> F
        E --> G
    end

    subgraph RAG["📚 RAG Pipeline"]
        I[PDF Upload + RAG]
        J[(Qdrant Vector DB)]
        I --> J
    end

    subgraph VOICE["🎤 Voice AI"]
        K[Voice Integration]
        L[Deepgram API]
        K --> L
    end

    subgraph TOOLS["🛠️ External Tools"]
        O[API Integration]
        P[3rd Party Tools]
        O --> P
    end

    A --> D
    A --> I
    A --> K
    A --> O

    classDef core fill:#ff9800,stroke:#333,color:#fff
    classDef db fill:#4caf50,stroke:#333,color:#fff
    classDef api fill:#2196f3,stroke:#333,color:#fff
    class A core
    class F,G,J db
    class E,L,P api
```

> 💬 **Chat Engine** (OpenAI + Postgres + Redis) → 📚 **RAG Pipeline** (Qdrant) → 🎤 **Voice AI** (Deepgram) → 🛠️ **External Tools**

<br/>

## 🛠️ Tech Stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=for-the-badge&logo=qdrant&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)
![Deepgram](https://img.shields.io/badge/Deepgram-13EF93?style=for-the-badge&logo=data:image/png;base64,&logoColor=black)

</div>

<br/>

## 📂 Project Structure

```
Aroma-Ai/
├── Agent/              # Core AI agent logic
├── alembic/             # Database migrations
├── crud/                # Database CRUD operations
├── docker/               # Docker configuration
├── frontend/             # Frontend (TypeScript) app
├── models/               # Data models
├── create_tables.py      # DB table initialization
├── db.py                 # Database connection setup
├── main.py                # FastAPI application entry point
├── redis_client.py        # Redis caching client
└── requirements.txt        # Python dependencies
```

<br/>

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js (for the frontend)
- PostgreSQL
- Redis
- Qdrant (vector database)
- Docker (optional, recommended)

### 1️⃣ Clone the repository
```bash
git clone https://github.com/Rohan77ux/Aroma-Ai.git
cd Aroma-Ai
```

### 2️⃣ Set up the backend
```bash
pip install -r requirements.txt
python create_tables.py
uvicorn main:app --reload
```

### 3️⃣ Set up the frontend
```bash
cd frontend
npm install
npm run dev
```

### 4️⃣ Run with Docker (optional)
```bash
cd docker
docker-compose up --build
```

<br/>

## ⚙️ Environment Variables

Create a `.env` file in the root directory with the following (adjust as needed for your setup):

```env
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
DATABASE_URL=postgresql://user:password@localhost:5432/aromadb
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
```

<br/>

## 🗺️ Roadmap

- [x] Smart conversational chat
- [x] Voice-based interaction
- [x] PDF upload & RAG-based Q&A
- [ ] Multi-document conversation memory
- [ ] Mobile-friendly UI improvements
- [ ] More third-party tool integrations

<br/>

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<br/>

## 📜 License

This project is licensed under the **MIT License**.

<br/>

<div align="center">

### 💛 Show some love by starring this repo!

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=12,20,6&height=120&section=footer" />

</div>


# aroma-multiagent-platform
