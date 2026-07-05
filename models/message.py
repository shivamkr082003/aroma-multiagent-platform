from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from db import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    user_id = Column(String, index=True)
    role = Column(String)
    content = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 🔥 relationship
    session = relationship("Session", back_populates="messages")