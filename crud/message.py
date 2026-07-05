from sqlalchemy.orm import Session
from models.message import Message
from models.session import Session as SessionModel


def create_message(db: Session, session_id, user_id, role, content):
    msg = Message(
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content
    )

    db.add(msg)

    # 🔥 Better title logic
    if role == "user":
        session = db.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()

        if session and (not session.title or session.title == "New Chat"):
            summary = content[:40]  # better than 2 words
            session.title = summary
            db.add(session)

    db.commit()
    db.refresh(msg)

    return msg


def get_messages(db: Session, session_id, limit=50):
    return db.query(Message)\
        .filter(Message.session_id == session_id)\
        .order_by(Message.created_at)\
        .limit(limit)\
        .all()
        
        
        