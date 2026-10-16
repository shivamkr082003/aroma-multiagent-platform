"""Register, sign in, sign out and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import get_db
from models.user import User

from . import rate_limit
from .deps import get_current_user
from .google import GoogleTokenError, client_id as google_client_id, verify_id_token
from .schemas import GoogleLoginRequest, LoginRequest, RegisterRequest, UserResponse
from .security import DUMMY_PASSWORD_HASH, cookie_settings, create_token, hash_password, token_ttl, verify_password

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


def _start_session(response: Response, user: User) -> None:
    response.set_cookie(value=create_token(user.id), max_age=int(token_ttl().total_seconds()), **cookie_settings())


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@auth_router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    user = User(email=data.email, name=data.name, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two sign-ups with the same email at once
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")
    db.refresh(user)
    _start_session(response, user)
    return user


@auth_router.post("/login", response_model=UserResponse)
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    if rate_limit.is_blocked(data.email, ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Please wait a few minutes and try again.")

    user = db.query(User).filter_by(email=data.email).first()
    # Google-only accounts have no password; check against the dummy hash so
    # the response (and its timing) looks like any wrong password.
    stored_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    password_ok = verify_password(data.password, stored_hash) and bool(user and user.password_hash)
    if not user or not password_ok:
        rate_limit.record_failure(data.email, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")

    rate_limit.clear_failures(data.email)
    _start_session(response, user)
    return user


@auth_router.get("/config")
def auth_config():
    """Public settings the sign-in page needs (the Google client ID is not a secret)."""
    return {"google_client_id": google_client_id()}


@auth_router.post("/google", response_model=UserResponse)
def google_login(data: GoogleLoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        claims = verify_id_token(data.credential)
    except GoogleTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))

    email, sub = claims["email"].strip().lower(), claims["sub"]
    user = db.query(User).filter_by(google_sub=sub).first()
    if not user:
        user = db.query(User).filter_by(email=email).first()
        if user and user.google_sub and user.google_sub != sub:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="This email is linked to a different Google account.")
        if user:
            # Link the existing account. Aroma never verified that email, so a
            # password set by whoever registered it first could belong to an
            # attacker who pre-created the account: drop it. The owner, now
            # proven by Google, signs in with Google from here on.
            user.google_sub = sub
            user.password_hash = None
        else:
            user = User(email=email, name=(claims.get("name") or email.split("@")[0])[:100],
                        password_hash=None, google_sub=sub)
            db.add(user)
    try:
        db.commit()
    except IntegrityError:  # the same Google account signing in twice at once
        db.rollback()
        user = db.query(User).filter_by(google_sub=sub).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Please try again.")
    db.refresh(user)
    _start_session(response, user)
    return user


@auth_router.post("/logout", status_code=204)
def logout():
    settings = cookie_settings()
    response = Response(status_code=204)
    response.delete_cookie(settings["key"], path=settings["path"], secure=settings["secure"],
                           httponly=True, samesite=settings["samesite"])
    return response


@auth_router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
