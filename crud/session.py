from models.session import Session

def create_session(db, session_id, user_id):
    existing = db.query(Session).filter(Session.id == session_id).first()

    if existing:
        return existing  # ✅ don't create again

    session = Session(
        id=session_id,
        user_id=user_id,
        title="New Chat"
    )

    db.add(session)
    db.commit()
    return session


def get_sessions(db, user_id):
    return db.query(Session).filter(Session.user_id == user_id).all()