import uuid

from sqlalchemy import Column, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from db import Base


class PromptTemplate(Base):
    """A user's saved prompt (built-in templates live in the frontend)."""

    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
