"""Password hashing and session tokens.

Configuration (environment variables, read at call time):
- AUTH_SECRET_KEY: signs session tokens. Required; generate with
  python -c "import secrets; print(secrets.token_urlsafe(48))"
- AUTH_TOKEN_TTL_HOURS: session lifetime (default 168 = 7 days).
- AUTH_COOKIE_SECURE / AUTH_COOKIE_SAMESITE: cookie flags. Local dev uses the
  defaults (false / lax). When the frontend and API are on different sites in
  production, set AUTH_COOKIE_SECURE=true and AUTH_COOKIE_SAMESITE=none.
"""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

COOKIE_NAME = "aroma_session"
_ALGORITHM = "HS256"

# scrypt parameters (OWASP-recommended minimum: N=2^17 is better on servers
# with spare memory; 2^14 keeps login fast on small free-tier instances).
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


# ===========================
#  PASSWORDS
# ===========================
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return "$".join([
        "scrypt", str(_SCRYPT_N), str(_SCRYPT_R), str(_SCRYPT_P),
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode(),
    ])


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified against when the email is unknown, so a login for a missing account
# takes as long as one with a wrong password (no account enumeration by timing).
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


# ===========================
#  SESSION TOKENS (JWT)
# ===========================
def _secret() -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "").strip()
    if len(secret) < 32:
        raise RuntimeError("AUTH_SECRET_KEY must be set to a random value of at least 32 characters.")
    return secret


def token_ttl() -> timedelta:
    return timedelta(hours=float(os.getenv("AUTH_TOKEN_TTL_HOURS", "168")))


def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + token_ttl()}, _secret(), algorithm=_ALGORITHM)


def decode_token(token: str) -> str | None:
    """Return the user id for a valid token, or None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM], options={"require": ["sub", "exp"]})
    except jwt.PyJWTError:
        return None
    return payload["sub"]


def cookie_settings() -> dict:
    samesite = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    secure = os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() in ("1", "true", "yes")
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": secure or samesite == "none",  # browsers reject SameSite=None without Secure
        "samesite": samesite,
        "path": "/",
    }
