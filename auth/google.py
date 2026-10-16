"""Verify "Sign in with Google" ID tokens (Google Identity Services).

The browser gets a signed ID token (a JWT) from Google and posts it to
/auth/google. It is trusted only after checking Google's signature (keys from
Google's JWKS endpoint), that it was issued for *our* client ID, that it comes
from Google, hasn't expired, and that Google verified the email address.

GOOGLE_CLIENT_ID (env): the OAuth "Web application" client ID. Unset = the
Google button is hidden and /auth/google refuses.
"""

import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"


class GoogleTokenError(Exception):
    """The credential is missing, forged, expired, or not for this app."""


def client_id() -> str | None:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip() or None


@lru_cache(maxsize=1)
def _jwks() -> PyJWKClient:
    # Google rotates its keys; PyJWKClient caches them and refetches on a new key id.
    return PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True, lifespan=3600)


def verify_id_token(token: str) -> dict:
    audience = client_id()
    if not audience:
        raise GoogleTokenError("Google sign-in is not configured on this server.")
    try:
        key = _jwks().get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=audience, leeway=30,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError as error:
        raise GoogleTokenError("Google sign-in failed. Please try again.") from error
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenError("Google sign-in failed. Please try again.")
    if not claims.get("email") or claims.get("email_verified") is not True:
        raise GoogleTokenError("Your Google account's email address isn't verified.")
    return claims
