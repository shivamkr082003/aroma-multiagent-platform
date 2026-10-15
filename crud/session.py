from fastapi import HTTPException

from models.session import Session
from models.message import Message  # noqa: F401

def create_session(db, session_id, user_id, project_id=None):
    existing = db.query(Session).filter(Session.id == session_id).first()

    if existing:
        # Session ids come from the client; never let one user write into
        # another user's chat. 404 so ids of other users' sessions don't leak.
        if existing.user_id != user_id:
            raise HTTPException(status_code=404, detail="Chat not found.")
        return existing  # ✅ don't create again

    session = Session(
        id=session_id,
        user_id=user_id,
        title="New Chat",
        project_id=project_id,  # ownership checked by the caller
    )

    db.add(session)
    db.commit()
    return session


def get_sessions(db, user_id):
    return db.query(Session).filter(Session.user_id == user_id).all()


def user_owns_session(db, session_id, user_id) -> bool:
    return db.query(Session).filter(Session.id == session_id, Session.user_id == user_id).first() is not None



def get_owned_session(db, session_id, user_id):
    session = db.query(Session).filter(Session.id == session_id, Session.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return session
