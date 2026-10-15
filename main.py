from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import os
import uuid
import requests
import ffmpeg
import json
# ✅ FIXED IMPORT (OLD SDK COMPATIBLE)
from deepgram import DeepgramClient

from Agent.agent import achat, achat_stream
from mcp_client.manager import mcp_manager
from mcp_client.router import mcp_router
from auth import auth_router, get_current_user
from db import get_db
from models.user import User
from crud.project import get_owned_project
from crud.session import create_session
from routers import projects as projects_router, sessions as sessions_router
from routers import stats as stats_router, templates as templates_router
from crud.message import create_message

from documents import ingest
from rag_store import ensure_collection
from retrieval import current_mode, get_reranker

app = FastAPI()
app.include_router(auth_router)
app.include_router(mcp_router)
app.include_router(sessions_router.router)
app.include_router(projects_router.router)
app.include_router(templates_router.router)
app.include_router(stats_router.router)


@app.on_event("shutdown")
async def shutdown_mcp_connections():
    await mcp_manager.shutdown()

# 🔊 serve audio files
os.makedirs("audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="audio"), name="audio")


# ===========================
# CORS
# ===========================
app.add_middleware(
    CORSMiddleware,
    # Browsers reject the combination of credentialed requests and a
    # wildcard origin. Keep local Next.js development origins explicit.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================
# Request schema
# ===========================
class ChatRequest(BaseModel):
    message: str
    session_id: str
    file_id: Optional[str] = None
    project_id: Optional[str] = None  # only used when this message starts a new chat


# ===========================
# Qdrant Setup
# ===========================
@app.on_event("startup")
def startup():
    # Also loads the embedding model once, so the first upload isn't slow.
    ensure_collection()
    if current_mode() == "hybrid_rerank":
        get_reranker()  # same for the reranker and the first document question

@app.get("/")
def home():
    return {
        "message": "Backend is running!",
        "docs": "/docs"
    }
# ===========================
# Upload API
# ===========================
@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    await run_in_threadpool(create_session, db, session_id, user.id)
    file_bytes = await file.read()
    # Extraction and embedding run on the CPU; keep them off the event loop.
    file_id = await run_in_threadpool(ingest, file_bytes, file.filename, user_id=user.id, session_id=session_id)
    if file_id is None:
        return {"error": "Unsupported file"}
    return {"file_id": file_id}
 

# ===========================
# Chat API
# ===========================
def _open_chat(db: Session, req: ChatRequest, user_id: str) -> str | None:
    """Create the chat on its first message and return the project it belongs to."""
    project_id = get_owned_project(db, req.project_id, user_id).id if req.project_id else None
    return create_session(db, req.session_id, user_id, project_id).project_id


@app.post("/chat")
async def chat_api(req: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = user.id

    # DB helpers are synchronous; keep them off the event loop.
    project_id = await run_in_threadpool(_open_chat, db, req, user_id)
    await run_in_threadpool(create_message, db, req.session_id, user_id, "user", req.message)

    response = await achat(req.message, req.session_id, req.file_id, user_id, project_id)

    await run_in_threadpool(create_message, db, req.session_id, user_id, "ai", response)

    return {"response": response}


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Server-Sent Events: live status, sources and answer tokens (see achat_stream)."""
    project_id = await run_in_threadpool(_open_chat, db, req, user.id)
    await run_in_threadpool(create_message, db, req.session_id, user.id, "user", req.message)
    # The request's DB session is closed before streaming starts, so save the
    # answer with a fresh session on the same connection pool.
    bind = db.get_bind()

    async def events():
        async for event in achat_stream(req.message, req.session_id, req.file_id, user.id, project_id):
            if event["type"] == "done":
                def save():
                    with Session(bind=bind) as save_db:
                        create_message(save_db, req.session_id, user.id, "ai", event["response"], event["sources"])
                await run_in_threadpool(save)
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # Disable proxy buffering so tokens reach the browser immediately.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===========================
# 🎤 SPEECH TO TEXT / 🔊 TEXT TO SPEECH (Deepgram)
# ===========================
class VoiceServiceError(Exception):
    """Deepgram could not be reached or rejected the request."""


def speech_to_text(audio_path: str) -> str:
    """Transcribe any browser recording (webm/opus, mp4/aac, ogg). Blocking."""
    wav_path = f"{audio_path}.wav"
    try:
        # ffmpeg detects the real container, so Safari's mp4 works too.
        (
            ffmpeg.input(audio_path)
            .output(wav_path, format="wav", acodec="pcm_s16le", ac=1, ar="16000")
            .run(overwrite_output=True, quiet=True)
        )
        with open(wav_path, "rb") as audio:
            res = requests.post(
                "https://api.deepgram.com/v1/listen",
                headers={"Authorization": f"Token {os.getenv('DEEPGRAM_API_KEY')}", "Content-Type": "audio/wav"},
                params={"model": "nova-2", "smart_format": "true"},
                data=audio,
                timeout=30,
            )
    except ffmpeg.Error as e:
        raise ValueError("The recording could not be read.") from e
    except requests.RequestException as e:
        raise VoiceServiceError(f"Deepgram unreachable: {e}") from e
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    if res.status_code != 200:
        raise VoiceServiceError(f"Deepgram STT {res.status_code}: {res.text[:200]}")
    data = res.json()
    return (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
        .get("transcript", "")
        .strip()
    )


def text_to_speech(text: str) -> str | None:
    """Return the URL of an MP3 of the reply, or None if TTS failed (the text reply still works). Blocking."""
    try:
        res = requests.post(
            "https://api.deepgram.com/v1/speak?model=aura-asteria-en",
            headers={"Authorization": f"Token {os.getenv('DEEPGRAM_API_KEY')}", "Content-Type": "application/json"},
            json={"text": text[:2000]},  # long answers: speak the start, show the full text
            timeout=30,
        )
    except requests.RequestException as e:
        print("❌ TTS:", e)
        return None
    if res.status_code != 200 or not res.headers.get("content-type", "").startswith("audio"):
        # Never save an error body as an .mp3: the player would show a broken file.
        print("❌ TTS:", res.status_code, res.text[:200])
        return None
    file = f"audio/{uuid.uuid4()}.mp3"
    with open(file, "wb") as f:
        f.write(res.content)
    return f"/{file}"


# ===========================
# 🎤 VOICE API
# ===========================
@app.post("/voice")
async def voice(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    project_id: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Spoken question in, text + spoken answer out. With session_id it joins that chat like a typed message."""
    input_file = f"temp_{uuid.uuid4()}.audio"
    try:
        with open(input_file, "wb") as f:
            f.write(await file.read())
        try:
            text = await run_in_threadpool(speech_to_text, input_file)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except VoiceServiceError as e:
            print("❌ STT:", e)
            raise HTTPException(status_code=502, detail="Speech recognition is unavailable right now. Please type instead.")
    finally:
        if os.path.exists(input_file):
            os.remove(input_file)

    if not text:
        raise HTTPException(status_code=422, detail="I couldn't hear anything. Try speaking a little closer to the mic.")

    if session_id:
        req = ChatRequest(message=text, session_id=session_id, project_id=project_id)
        chat_project = await run_in_threadpool(_open_chat, db, req, user.id)
        await run_in_threadpool(create_message, db, session_id, user.id, "user", text)
        response = await achat(text, session_id, None, user.id, chat_project)
        await run_in_threadpool(create_message, db, session_id, user.id, "ai", response)
    else:
        # One voice history per user, so users never share Redis chat context.
        response = await achat(text, f"voice_{user.id}", user_id=user.id)

    audio = await run_in_threadpool(text_to_speech, response)
    return {"user_text": text, "response": response, "audio_url": audio}
