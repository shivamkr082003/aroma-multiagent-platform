import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db as db_module
import main
from auth import rate_limit
from auth.security import COOKIE_NAME, verify_password
from db import Base
from models.user import User

PASSWORD = "aroma2026pass"


class FakeRedis:
    """Just enough of redis-py for the login rate limiter."""

    def __init__(self):
        self.data: dict[str, int] = {}

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
    fake_redis = FakeRedis()
    monkeypatch.setattr("redis_client.redis_client", fake_redis)

    async def fake_achat(message, session_id, file_id=None, user_id="demo_user", project_id=None):
        return f"echo: {message}"

    monkeypatch.setattr(main, "achat", fake_achat)
    yield
    main.app.dependency_overrides.clear()


def new_client():
    # Not used as a context manager, so startup hooks (Qdrant) don't run.
    return TestClient(main.app)


def register(client, email="shivam@example.com", name="Shivam", password=PASSWORD):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password})


# ===========================
#  REGISTER / LOGIN / LOGOUT
# ===========================
def test_register_signs_in_and_hashes_password(session_factory):
    client = new_client()
    response = register(client, email="  Shivam@Example.com ")
    assert response.status_code == 201
    assert response.json()["email"] == "shivam@example.com"
    assert "password" not in response.text
    cookie = response.headers["set-cookie"]
    assert COOKIE_NAME in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie

    assert client.get("/auth/me").json()["name"] == "Shivam"

    with session_factory() as db:
        stored = db.query(User).one().password_hash
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert verify_password(PASSWORD, stored)


def test_register_rejects_duplicate_email_case_insensitively():
    client = new_client()
    register(client)
    response = register(new_client(), email="SHIVAM@example.com")
    assert response.status_code == 409


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678"])
def test_register_rejects_weak_password(password):
    assert register(new_client(), password=password).status_code == 422


def test_login_and_logout():
    register(new_client())
    client = new_client()
    assert client.get("/auth/me").status_code == 401

    response = client.post("/auth/login", json={"email": "Shivam@example.com", "password": PASSWORD})
    assert response.status_code == 200
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_wrong_password_and_unknown_email_look_the_same():
    register(new_client())
    wrong = new_client().post("/auth/login", json={"email": "shivam@example.com", "password": "nope12345"})
    unknown = new_client().post("/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_is_rate_limited_after_repeated_failures():
    register(new_client())
    client = new_client()
    for _ in range(rate_limit.MAX_FAILURES_PER_EMAIL):
        assert client.post("/auth/login", json={"email": "shivam@example.com", "password": "wrong1234"}).status_code == 401
    # Even the right password is refused until the window passes.
    response = client.post("/auth/login", json={"email": "shivam@example.com", "password": PASSWORD})
    assert response.status_code == 429


@pytest.mark.parametrize("token_kind", ["garbage", "wrong_secret", "expired"])
def test_invalid_tokens_are_rejected(token_kind):
    user_id = register(new_client()).json()["id"]
    now = datetime.now(timezone.utc)
    tokens = {
        "garbage": "not-a-jwt",
        "wrong_secret": jwt.encode({"sub": user_id, "exp": now + timedelta(hours=1)}, "x" * 48, algorithm="HS256"),
        "expired": jwt.encode({"sub": user_id, "exp": now - timedelta(seconds=1)},
                              "test-secret-key-that-is-long-enough-for-hs256", algorithm="HS256"),
    }
    client = new_client()
    client.cookies.set(COOKIE_NAME, tokens[token_kind])
    assert client.get("/auth/me").status_code == 401


# ===========================
#  PROTECTED ENDPOINTS
# ===========================
@pytest.mark.parametrize("method,path", [
    ("post", "/chat"), ("get", "/sessions"), ("get", "/messages/s1"),
    ("post", "/upload"), ("post", "/voice"), ("get", "/mcp/servers"),
])
def test_endpoints_require_sign_in(method, path):
    assert getattr(new_client(), method)(path).status_code == 401


def test_users_cannot_see_or_write_each_others_chats():
    alice, bob = new_client(), new_client()
    register(alice, email="alice@example.com", name="Alice")
    register(bob, email="bob@example.com", name="Bob")

    response = alice.post("/chat", json={"message": "hello", "session_id": "s-alice"})
    assert response.json() == {"response": "echo: hello"}

    assert [s["id"] for s in alice.get("/sessions").json()] == ["s-alice"]
    assert alice.get("/messages/s-alice").json()[0]["content"] == "hello"

    assert bob.get("/sessions").json() == []
    assert bob.get("/messages/s-alice").status_code == 404
    assert bob.post("/chat", json={"message": "hijack", "session_id": "s-alice"}).status_code == 404
    assert len(alice.get("/messages/s-alice").json()) == 2  # bob's message never landed


def test_chat_stream_sends_events_and_saves_sources(monkeypatch):
    sources = [{"id": 1, "type": "document", "title": "zephyr.pdf", "page": 1, "snippet": "Team lead"}]

    async def fake_stream(message, session_id, file_id=None, user_id="demo_user", project_id=None):
        yield {"type": "status", "label": "Reading your documents…"}
        yield {"type": "sources", "sources": sources}
        yield {"type": "token", "text": "Ananya "}
        yield {"type": "token", "text": "Rao [1]"}
        yield {"type": "done", "response": "Ananya Rao [1]", "sources": sources}

    monkeypatch.setattr(main, "achat_stream", fake_stream)
    client = new_client()
    register(client)

    response = client.post("/chat/stream", json={"message": "who leads?", "session_id": "s-stream"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in response.text.split("\n\n") if line.startswith("data: ")]
    assert [e["type"] for e in events] == ["status", "sources", "token", "token", "done"]

    saved = client.get("/messages/s-stream").json()
    assert saved[1] == {"role": "ai", "content": "Ananya Rao [1]", "sources": sources}


# ===========================
#  VOICE
# ===========================
def voice_upload(client, **form):
    return client.post("/voice", files={"file": ("voice.webm", b"fake-audio", "audio/webm")}, data=form)


def test_voice_joins_the_open_chat(monkeypatch):
    monkeypatch.setattr(main, "speech_to_text", lambda path: "what is the capital of france")
    monkeypatch.setattr(main, "text_to_speech", lambda text: "/audio/reply.mp3")
    client = new_client()
    register(client)

    response = voice_upload(client, session_id="voice-chat")
    assert response.status_code == 200
    assert response.json() == {"user_text": "what is the capital of france",
                               "response": "echo: what is the capital of france", "audio_url": "/audio/reply.mp3"}
    saved = client.get("/messages/voice-chat").json()
    assert [(m["role"], m["content"]) for m in saved] == [
        ("user", "what is the capital of france"), ("ai", "echo: what is the capital of france")]


@pytest.mark.parametrize("stt,status,needle", [
    (lambda path: "", 422, "couldn't hear"),
    ("service_error", 502, "unavailable"),
    ("bad_audio", 422, "could not be read"),
])
def test_voice_errors_are_clear(monkeypatch, stt, status, needle):
    def failing(path):
        if stt == "service_error":
            raise main.VoiceServiceError("deepgram 401")
        raise ValueError("The recording could not be read.")

    monkeypatch.setattr(main, "speech_to_text", stt if callable(stt) else failing)
    client = new_client()
    register(client)
    response = voice_upload(client, session_id="v1")
    assert response.status_code == status and needle in response.json()["detail"]


def test_voice_still_answers_when_tts_fails(monkeypatch):
    monkeypatch.setattr(main, "speech_to_text", lambda path: "hello")
    monkeypatch.setattr(main, "text_to_speech", lambda text: None)
    client = new_client()
    register(client)
    body = voice_upload(client).json()  # no session: standalone voice turn
    assert body["response"] == "echo: hello" and body["audio_url"] is None


def test_voice_cannot_write_into_someone_elses_chat(monkeypatch):
    monkeypatch.setattr(main, "speech_to_text", lambda path: "hijack")
    monkeypatch.setattr(main, "text_to_speech", lambda text: None)
    alice, bob = new_client(), new_client()
    register(alice, email="alice@example.com")
    register(bob, email="bob@example.com")
    alice.post("/chat", json={"message": "mine", "session_id": "alice-chat"})
    assert voice_upload(bob, session_id="alice-chat").status_code == 404
