from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import fitz
import os
import uuid
import requests
import ffmpeg
import hashlib
# ✅ FIXED IMPORT (OLD SDK COMPATIBLE)
from deepgram import DeepgramClient

from Agent.agent import chat
from db import SessionLocal
from crud.session import create_session, get_sessions
from crud.message import create_message, get_messages
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, Docx2txtLoader
)

from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from qdrant_client.models import VectorParams, Distance,Filter, FieldCondition, MatchValue
GAP_THRESHOLD_PT = 1.5

# ===========================
# DB Dependency
# ===========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()

# 🔊 serve audio files
os.makedirs("audio", exist_ok=True)
app.mount("/audio", StaticFiles(directory="audio"), name="audio")


# ===========================
# CORS
# ===========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


# ===========================
# Qdrant Setup
# ===========================
qdrant_client = QdrantClient(url="http://localhost:6333")

@app.on_event("startup")
def startup():
    try:
        qdrant_client.get_collection("docs")
    except:
        qdrant_client.create_collection(
            collection_name="docs",
            vectors_config=VectorParams(
                size=1536,
                distance=Distance.COSINE,
            ),
        )

@app.get("/")
def home():
    return {
        "message": "Backend is running!",
        "docs": "/docs"
    }
# ===========================
# Upload API
# ===========================
def _reconstruct_line(spans: list[tuple[float, float, str]]) -> str:
    """
    spans: list of (x0, x1, text) for one visual line, sorted by x0.
    Inserts a space wherever the horizontal gap between spans exceeds
    GAP_THRESHOLD_PT — purely based on geometry, no word lists, no
    domain knowledge. Works identically for names, URLs, code, numbers,
    or anything else.
    """
    if not spans:
        return ""
    out = spans[0][2]
    prev_x1 = spans[0][1]
    for x0, x1, text in spans[1:]:
        gap = x0 - prev_x1
        if gap > GAP_THRESHOLD_PT and not out.endswith(" ") and not text.startswith(" "):
            out += " "
        out += text
        prev_x1 = x1
    return out
 
 
def extract_pdf_text_layout_aware(file_path: str) -> list[Document]:
    """
    Extract text from a PDF using span-level layout data so visually
    separate text (different columns, icon-prefixed rows, adjacent
    links with no embedded space) gets a space between it, even when
    the PDF itself never included a space character there. Returns one
    LangChain Document per page.
    """
    docs = []
    pdf = fitz.open(file_path)
 
    for page_num, page in enumerate(pdf):
        raw = page.get_text("dict")
        lines_text = []
 
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                spans = []
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append((x0, x1, text))
                spans.sort(key=lambda s: s[0])  # left to right
                if spans:
                    lines_text.append(_reconstruct_line(spans))
 
        page_text = "\n".join(lines_text)
        docs.append(
            Document(
                page_content=page_text,
                metadata={"source": file_path, "page": page_num},
            )
        )
 
    pdf.close()
    return docs
 
 
def load_document(file_location: str, ext: str):
    """Load a document with the best available extraction for its type."""
    if ext == ".pdf":
        return extract_pdf_text_layout_aware(file_location)
    elif ext == ".txt":
        return TextLoader(file_location).load()
    elif ext == ".docx":
        return Docx2txtLoader(file_location).load()
    else:
        return None
 
 
# ===========================
#  DUPLICATE UPLOAD DETECTION
#
#  Hash the raw file bytes (content-based, not filename-based — so a
#  renamed copy of the same PDF is still recognized as a duplicate).
#  Before chunking/embedding, check Qdrant for any existing chunk with
#  the same file_hash. If found, skip processing entirely and just
#  return the existing file_id — silently, with no indication to the
#  user that this was a duplicate. The response shape is identical
#  either way, so the frontend can't tell the difference.
# ===========================
def compute_file_hash(file_bytes: bytes) -> str:
    """SHA-256 hash of the raw file contents."""
    return hashlib.sha256(file_bytes).hexdigest()
 
 
def find_existing_file_id(file_hash: str) -> str | None:
    """
    Look up Qdrant for any previously-stored chunk with this exact
    file_hash. Returns the existing file_id if found, else None.
    """
    client = qdrant_client  # already initialized elsewhere in the app
 
    results, _ = client.scroll(
        collection_name="docs",
        scroll_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.file_hash",
                    match=MatchValue(value=file_hash),
                )
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
 
    if results:
        payload = results[0].payload or {}
        # langchain-qdrant nests user metadata under "metadata"
        metadata = payload.get("metadata", payload)
        return metadata.get("file_id")
 
    return None
 
 
@app.post("/upload")
async def upload(file: UploadFile = File(...), session_id: str = Form(...)):
    ext = os.path.splitext(file.filename)[1].lower()
    file_bytes = await file.read()
 
    # 1. Hash the raw content and check if we've already stored this
    #    exact file before. If so, skip extraction/chunking/embedding
    #    entirely and silently reuse the existing file_id — no error,
    #    no special message, response shape identical to a fresh upload.
    file_hash = compute_file_hash(file_bytes)
    existing_file_id = find_existing_file_id(file_hash)
    if existing_file_id:
        return {"file_id": existing_file_id}
 
    # 2. Not a duplicate — process normally.
    file_id = str(uuid.uuid4())
    file_location = f"temp_{file_id}{ext}"
 
    with open(file_location, "wb") as f:
        f.write(file_bytes)
 
    docs = load_document(file_location, ext)
 
    if docs is None:
        os.remove(file_location)
        return {"error": "Unsupported file"}
 
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    chunks = splitter.split_documents(docs)
 
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
 
    for chunk in chunks:
        chunk.metadata["file_id"] = file_id
        chunk.metadata["session_id"] = session_id
        chunk.metadata["file_hash"] = file_hash
 
    vectorstore = QdrantVectorStore(
        client=qdrant_client,
        collection_name="docs",
        embedding=embeddings,
    )
 
    vectorstore.add_documents(chunks)
    os.remove(file_location)
 
    return {"file_id": file_id}
 

# ===========================
# Chat API
# ===========================
@app.post("/chat")
def chat_api(req: ChatRequest, db: Session = Depends(get_db)):
    user_id = "demo_user"

    create_session(db, req.session_id, user_id)
    create_message(db, req.session_id, user_id, "user", req.message)

    response = chat(req.message, req.session_id, req.file_id)

    create_message(db, req.session_id, user_id, "ai", response)

    return {"response": response}


# ===========================
# Sessions API
# ===========================
@app.get("/sessions")
def sessions(db: Session = Depends(get_db)):
    return get_sessions(db, "demo_user")


@app.get("/messages/{session_id}")
def messages(session_id: str, db: Session = Depends(get_db)):
    msgs = get_messages(db, session_id)
    return [{"role": m.role, "content": m.content} for m in msgs]


# ===========================
# 🎤 SPEECH TO TEXT (FIXED)
# ===========================
def speech_to_text(audio_path: str):
    try:
        api_key = os.getenv("DEEPGRAM_API_KEY")

        wav_path = audio_path.replace(".webm", ".wav")

        # Convert webm → wav
        (
            ffmpeg.input(audio_path)
            .output(wav_path, format="wav", acodec="pcm_s16le", ac=1, ar="16000")
            .run(overwrite_output=True, quiet=True)
        )

        with open(wav_path, "rb") as audio:
            res = requests.post(
                "https://api.deepgram.com/v1/listen",
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": "audio/wav"
                },
                params={
                    "model": "nova-2",
                    "smart_format": "true"
                },
                data=audio
            )

        data = res.json()

        transcript = (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )

        os.remove(wav_path)

        return transcript

    except Exception as e:
        print("❌ STT:", str(e))
        return ""

# ===========================
# 🔊 TEXT TO SPEECH
# ===========================
def text_to_speech(text: str):
    try:
        res = requests.post(
            "https://api.deepgram.com/v1/speak?model=aura-asteria-en",
            headers={
                "Authorization": f"Token {os.getenv('DEEPGRAM_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={"text": text}
        )

        file = f"audio/{uuid.uuid4()}.mp3"
        with open(file, "wb") as f:
            f.write(res.content)

        return f"/{file}"

    except Exception as e:
        print("❌ TTS:", e)
        return None


# ===========================
# 🎤 VOICE API
# ===========================
@app.post("/voice")
async def voice(file: UploadFile = File(...)):
    input_file = f"temp_{uuid.uuid4()}.webm"

    try:
        with open(input_file, "wb") as f:
            f.write(await file.read())

        text = speech_to_text(input_file)

        if not text:
            return {"error": "No speech detected"}

        response = chat(text, "voice_session")

        audio = text_to_speech(response)

        return {
            "user_text": text,
            "response": response,
            "audio_url": audio
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        if os.path.exists(input_file):
            os.remove(input_file)