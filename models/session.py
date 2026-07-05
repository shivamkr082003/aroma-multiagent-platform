from sqlalchemy import Column, String, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    title = Column(String, default="New Chat")
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 🔥 relationship
    messages = relationship("Message", back_populates="session", cascade="all, delete")