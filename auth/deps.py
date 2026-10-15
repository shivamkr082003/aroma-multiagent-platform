"""FastAPI dependency that resolves the signed-in user."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db import get_db
from models.user import User

from .security import COOKIE_NAME, decode_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Browser clients send the httpOnly cookie; scripts can use a Bearer header.
    token = request.cookies.get(COOKIE_NAME)
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    user_id = decode_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    return user
