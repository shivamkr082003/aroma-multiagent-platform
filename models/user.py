import uuid

from sqlalchemy import Column, String, TIMESTAMP
from sqlalchemy.sql import func

from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)  # stored lower-cased
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=True)  # None for Google-only accounts
    google_sub = Column(String, unique=True, index=True, nullable=True)  # Google's stable account id
    created_at = Column(TIMESTAMP, server_default=func.now())
