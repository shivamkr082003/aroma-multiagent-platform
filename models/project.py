import uuid

from sqlalchemy import Column, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from db import Base


class Project(Base):
    """A workspace: documents uploaded here are shared by every chat in it."""

    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
