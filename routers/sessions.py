"""Chat list and management: list, read, rename, delete, clear all."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import get_current_user
from crud.message import get_messages
from crud.session import get_owned_session, user_owns_session
from db import get_db
from documents import delete_documents
from models.session import Session as ChatSession
from models.user import User
from redis_client import clear_chat

router = APIRouter(tags=["Chats"])


class SessionRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title can't be empty.")
        return value


def _session_json(s: ChatSession) -> dict:
    return {"id": s.id, "title": s.title, "created_at": s.created_at, "project_id": s.project_id}


def delete_chat(db: Session, chat: ChatSession, user_id: str) -> None:
    """Remove a chat everywhere: messages (cascade), Redis history and its uploaded documents."""
    session_id = chat.id
    db.delete(chat)
    db.commit()
    try:
        clear_chat(session_id)
    except Exception:
        pass  # Redis is a cache; a stale entry expires on its own
    delete_documents(user_id, session_id=session_id)


@router.get("/sessions")
def list_sessions(project_id: str | None = Query(None), user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    query = db.query(ChatSession).filter(ChatSession.user_id == user.id)
    if project_id:
        query = query.filter(ChatSession.project_id == project_id)
    return [_session_json(s) for s in query.order_by(ChatSession.created_at.desc()).all()]


@router.get("/messages/{session_id}")
def messages(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user_owns_session(db, session_id, user.id):
        raise HTTPException(status_code=404, detail="Chat not found.")
    return [{"role": m.role, "content": m.content, "sources": m.sources or []} for m in get_messages(db, session_id)]


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, data: SessionRename, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    chat = get_owned_session(db, session_id, user.id)
    chat.title = data.title
    db.commit()
    return _session_json(chat)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    chat = get_owned_session(db, session_id, user.id)
    await run_in_threadpool(delete_chat, db, chat, user.id)
    return Response(status_code=204)


@router.delete("/sessions", status_code=204)
async def clear_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete every chat outside projects. Project chats stay with their project."""
    chats = db.query(ChatSession).filter(ChatSession.user_id == user.id, ChatSession.project_id.is_(None)).all()
    for chat in chats:
        await run_in_threadpool(delete_chat, db, chat, user.id)
    return Response(status_code=204)
