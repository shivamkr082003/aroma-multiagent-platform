"""Projects, project documents, chat management, templates and statistics."""

import pytest
from fastapi.testclient import TestClient
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db as db_module
import documents
import main
from db import Base
from models.message import Message
from test_retrieval import HashEmbeddings

SOURCES = [{"id": 1, "type": "document", "title": "notes.txt", "page": None, "snippet": "x"}]


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)

    def pipeline(self):
        return self

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1

    def expire(self, *args, **kwargs):
        pass

    def execute(self):
        pass


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def app_deps(session_factory, monkeypatch):
    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[db_module.get_db] = get_db
    monkeypatch.setattr("redis_client.redis_client", FakeRedis())

    # Real document code against an in-memory Qdrant with tiny hash embeddings.
    client = QdrantClient(":memory:")
    client.create_collection("t", vectors_config=VectorParams(size=HashEmbeddings.dim, distance=Distance.COSINE))
    store = QdrantVectorStore(client=client, collection_name="t", embedding=HashEmbeddings())
    monkeypatch.setattr(documents, "qdrant_client", client)
    monkeypatch.setattr(documents, "collection_name", lambda: "t")
    monkeypatch.setattr(documents, "get_vectorstore", lambda: store)
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def agent_calls(monkeypatch):
    calls = []

    async def fake_stream(message, session_id, file_id=None, user_id="demo_user", project_id=None):
        calls.append({"session_id": session_id, "project_id": project_id})
        yield {"type": "done", "response": f"echo: {message}", "sources": SOURCES}

    monkeypatch.setattr(main, "achat_stream", fake_stream)
    return calls


def signed_in(email="alice@example.com"):
    client = TestClient(main.app)
    response = client.post("/auth/register", json={"name": email.split("@")[0], "email": email, "password": "aroma2026"})
    assert response.status_code == 201
    return client


def ask(client, message, session_id, project_id=None):
    body = {"message": message, "session_id": session_id}
    if project_id:
        body["project_id"] = project_id
    return client.post("/chat/stream", json=body)


# ===========================
#  PROJECTS
# ===========================
def test_project_crud_and_isolation():
    alice, bob = signed_in(), signed_in("bob@example.com")
    project = alice.post("/projects", json={"name": "  Final year  ", "description": "Thesis"}).json()
    assert project["name"] == "Final year" and project["chats"] == 0 and project["documents"] == 0

    assert alice.patch(f"/projects/{project['id']}", json={"name": "Thesis"}).json()["name"] == "Thesis"
    assert [p["id"] for p in alice.get("/projects").json()] == [project["id"]]

    assert bob.get("/projects").json() == []
    assert bob.get(f"/projects/{project['id']}").status_code == 404
    assert bob.delete(f"/projects/{project['id']}").status_code == 404
    assert alice.post("/projects", json={"name": "   "}).status_code == 422


def test_project_documents_upload_list_dedupe_delete():
    alice = signed_in()
    pid = alice.post("/projects", json={"name": "P"}).json()["id"]
    upload = lambda name, data: alice.post(f"/projects/{pid}/documents", files={"file": (name, data, "text/plain")})

    first = upload("notes.txt", b"The viva is on 3 March in room 204.")
    assert first.status_code == 201
    assert upload("copy.txt", b"The viva is on 3 March in room 204.").json() == first.json()  # same content
    assert upload("slides.pptx", b"x").status_code == 400

    docs = alice.get(f"/projects/{pid}/documents").json()
    assert [(d["file_name"], d["chunks"]) for d in docs] == [("notes.txt", 1)]
    assert alice.get(f"/projects/{pid}").json()["documents"] == 1

    assert signed_in("bob@example.com").get(f"/projects/{pid}/documents").status_code == 404

    assert alice.delete(f"/projects/{pid}/documents/{first.json()['file_id']}").status_code == 204
    assert alice.get(f"/projects/{pid}/documents").json() == []


def test_chats_inside_a_project_search_the_project(agent_calls):
    alice = signed_in()
    pid = alice.post("/projects", json={"name": "P"}).json()["id"]

    assert ask(alice, "first", "c1", project_id=pid).status_code == 200
    assert ask(alice, "follow-up", "c1").status_code == 200  # project remembered by the chat
    assert ask(alice, "plain chat", "c2").status_code == 200
    assert [c["project_id"] for c in agent_calls] == [pid, pid, None]

    assert [s["id"] for s in alice.get(f"/sessions?project_id={pid}").json()] == ["c1"]
    assert alice.get(f"/projects/{pid}").json()["chats"] == 1

    bob = signed_in("bob@example.com")
    assert ask(bob, "sneaky", "c3", project_id=pid).status_code == 404


def test_deleting_a_project_removes_its_chats_and_documents(agent_calls):
    alice = signed_in()
    pid = alice.post("/projects", json={"name": "P"}).json()["id"]
    alice.post(f"/projects/{pid}/documents", files={"file": ("a.txt", b"alpha", "text/plain")})
    ask(alice, "q", "c1", project_id=pid)
    ask(alice, "outside", "c2")

    assert alice.delete(f"/projects/{pid}").status_code == 204
    assert [s["id"] for s in alice.get("/sessions").json()] == ["c2"]
    assert documents.list_documents(alice.get("/auth/me").json()["id"], project_id=pid) == []


# ===========================
#  CHAT MANAGEMENT
# ===========================
def test_rename_delete_and_clear_chats(agent_calls, session_factory):
    alice = signed_in()
    pid = alice.post("/projects", json={"name": "P"}).json()["id"]
    for sid in ("c1", "c2"):
        ask(alice, "hello", sid)
    ask(alice, "in project", "c3", project_id=pid)

    assert alice.patch("/sessions/c1", json={"title": "  Exam prep "}).json()["title"] == "Exam prep"
    assert alice.patch("/sessions/c1", json={"title": "   "}).status_code == 422

    assert alice.delete("/sessions/c2").status_code == 204
    assert alice.get("/messages/c2").status_code == 404
    with session_factory() as db:
        assert db.query(Message).filter(Message.session_id == "c2").count() == 0

    bob = signed_in("bob@example.com")
    assert bob.delete("/sessions/c1").status_code == 404
    assert bob.patch("/sessions/c1", json={"title": "x"}).status_code == 404

    assert alice.delete("/sessions").status_code == 204  # clears chats outside projects only
    assert [s["id"] for s in alice.get("/sessions").json()] == ["c3"]


# ===========================
#  TEMPLATES
# ===========================
def test_templates_crud_and_isolation():
    alice, bob = signed_in(), signed_in("bob@example.com")
    template = alice.post("/templates", json={"title": "Viva prep", "prompt": "Ask me 5 viva questions on {topic}"})
    assert template.status_code == 201
    tid = template.json()["id"]

    assert [t["title"] for t in alice.get("/templates").json()] == ["Viva prep"]
    assert bob.get("/templates").json() == []
    assert bob.delete(f"/templates/{tid}").status_code == 404
    assert alice.post("/templates", json={"title": "x", "prompt": "  "}).status_code == 422
    assert alice.delete(f"/templates/{tid}").status_code == 204
    assert alice.get("/templates").json() == []


# ===========================
#  STATISTICS
# ===========================
def test_stats(agent_calls):
    alice = signed_in()
    pid = alice.post("/projects", json={"name": "P"}).json()["id"]
    alice.post(f"/projects/{pid}/documents", files={"file": ("notes.txt", b"alpha beta", "text/plain")})
    alice.post("/templates", json={"title": "t", "prompt": "p"})
    ask(alice, "q1", "c1")
    ask(alice, "q2", "c1")
    ask(alice, "q3", "c2", project_id=pid)

    stats = alice.get("/stats").json()
    assert stats["totals"] == {"chats": 2, "questions": 3, "documents": 1, "projects": 1, "templates": 1}
    assert len(stats["activity"]) == 14 and stats["activity"][-1]["questions"] == 3
    assert stats["grounding"] == {"documents": 3, "web": 0, "both": 0, "model": 0}
    assert stats["top_documents"] == [{"title": "notes.txt", "answers": 3}]
    assert stats["response_time"]["samples"] == 3

    assert signed_in("bob@example.com").get("/stats").json()["totals"]["questions"] == 0
