"""Projects (workspaces): named groups of documents shared by every chat inside them."""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from crud.project import get_owned_project
from db import get_db
from documents import SUPPORTED_EXTENSIONS, delete_documents, ingest, list_documents
from models.project import Project
from models.session import Session as ChatSession
from models.user import User

from .sessions import delete_chat

router = APIRouter(prefix="/projects", tags=["Projects"])


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Give the project a name.")
    return value


class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _clean_name(value)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return _clean_name(value) if value is not None else None


def _project_json(project: Project, chats: int, documents: int) -> dict:
    return {"id": project.id, "name": project.name, "description": project.description,
            "created_at": project.created_at, "chats": chats, "documents": documents}


def _chat_counts(db: Session, user_id: str) -> dict[str, int]:
    rows = (db.query(ChatSession.project_id, func.count(ChatSession.id))
            .filter(ChatSession.user_id == user_id, ChatSession.project_id.isnot(None))
            .group_by(ChatSession.project_id).all())
    return dict(rows)


@router.get("")
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.user_id == user.id).order_by(Project.created_at.desc()).all()
    chats = _chat_counts(db, user.id)
    return [_project_json(p, chats.get(p.id, 0), len(list_documents(user.id, project_id=p.id))) for p in projects]


@router.post("", status_code=201)
def create_project(data: ProjectIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = Project(user_id=user.id, name=data.name, description=(data.description or "").strip() or None)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_json(project, 0, 0)


@router.get("/{project_id}")
def get_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = get_owned_project(db, project_id, user.id)
    return _project_json(project, _chat_counts(db, user.id).get(project.id, 0),
                         len(list_documents(user.id, project_id=project.id)))


@router.patch("/{project_id}")
def update_project(project_id: str, data: ProjectUpdate, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    project = get_owned_project(db, project_id, user.id)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description.strip() or None
    db.commit()
    return get_project(project_id, user, db)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes the project, its documents and all of its chats."""
    project = get_owned_project(db, project_id, user.id)
    for chat in db.query(ChatSession).filter(ChatSession.project_id == project.id).all():
        await run_in_threadpool(delete_chat, db, chat, user.id)
    await run_in_threadpool(delete_documents, user.id, project_id=project.id)
    db.delete(project)
    db.commit()
    return Response(status_code=204)


@router.get("/{project_id}/documents")
def project_documents(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(db, project_id, user.id)
    return list_documents(user.id, project_id=project_id)


@router.post("/{project_id}/documents", status_code=201)
async def upload_project_document(project_id: str, file: UploadFile = File(...),
                                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_project(db, project_id, user.id)
    file_bytes = await file.read()
    file_id = await run_in_threadpool(ingest, file_bytes, file.filename, user_id=user.id, project_id=project_id)
    if file_id is None:
        raise HTTPException(status_code=400, detail=f"Unsupported file. Use {', '.join(SUPPORTED_EXTENSIONS)}.")
    return {"file_id": file_id}


@router.delete("/{project_id}/documents/{file_id}", status_code=204)
async def delete_project_document(project_id: str, file_id: str, user: User = Depends(get_current_user),
                                  db: Session = Depends(get_db)):
    get_owned_project(db, project_id, user.id)
    await run_in_threadpool(delete_documents, user.id, project_id=project_id, file_id=file_id)
    return Response(status_code=204)
