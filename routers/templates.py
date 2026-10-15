"""A user's saved prompt templates."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from models.template import PromptTemplate
from models.user import User

router = APIRouter(prefix="/templates", tags=["Templates"])


class TemplateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    prompt: str = Field(..., min_length=1, max_length=4000)

    @field_validator("title", "prompt")
    @classmethod
    def strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field can't be empty.")
        return value


def _json(t: PromptTemplate) -> dict:
    return {"id": t.id, "title": t.title, "prompt": t.prompt, "created_at": t.created_at}


@router.get("")
def list_templates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(PromptTemplate).filter(PromptTemplate.user_id == user.id).order_by(PromptTemplate.created_at.desc())
    return [_json(t) for t in rows.all()]


@router.post("", status_code=201)
def create_template(data: TemplateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    template = PromptTemplate(user_id=user.id, title=data.title, prompt=data.prompt)
    db.add(template)
    db.commit()
    db.refresh(template)
    return _json(template)


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    template = db.query(PromptTemplate).filter(PromptTemplate.id == template_id,
                                               PromptTemplate.user_id == user.id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    db.delete(template)
    db.commit()
    return Response(status_code=204)
