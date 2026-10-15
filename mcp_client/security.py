"""Security policy for MCP servers: STDIO allowlist, secret encryption, masking.

Configuration (environment variables, read at call time):
- MCP_ALLOW_STDIO: "true" to allow STDIO servers. Off by default, because a
  STDIO server runs a local process on the backend host.
- MCP_STDIO_ALLOWED_COMMANDS: comma-separated command names allowed when
  STDIO is on, e.g. "npx,uvx". Paths are not accepted.
- MCP_SECRET_KEY: Fernet key used to encrypt headers/env at rest. Generate with
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import json
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

MASK = "********"
_ENC_KEY = "__enc__"


class MCPPolicyError(ValueError):
    """A server configuration is not allowed by the backend's policy."""


# ===========================
#  STDIO POLICY
# ===========================
def stdio_allowed() -> bool:
    return os.getenv("MCP_ALLOW_STDIO", "false").strip().lower() in ("1", "true", "yes")


def stdio_allowed_commands() -> list[str]:
    raw = os.getenv("MCP_STDIO_ALLOWED_COMMANDS", "")
    return [cmd.strip() for cmd in raw.split(",") if cmd.strip()]


def check_transport_allowed(transport: str, command: str | None) -> None:
    if transport != "stdio":
        return
    if not stdio_allowed():
        raise MCPPolicyError("STDIO MCP servers are disabled on this backend (set MCP_ALLOW_STDIO=true).")
    if not command or "/" in command or "\\" in command:
        raise MCPPolicyError("STDIO command must be a bare command name, not a path.")
    allowed = stdio_allowed_commands()
    if command not in allowed:
        raise MCPPolicyError(
            f"STDIO command '{command}' is not allowed. Allowed: {', '.join(allowed) or 'none'} "
            "(configure MCP_STDIO_ALLOWED_COMMANDS)."
        )


# ===========================
#  SECRET ENCRYPTION
# ===========================
def _fernet() -> Fernet | None:
    key = os.getenv("MCP_SECRET_KEY", "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise MCPPolicyError("MCP_SECRET_KEY is not a valid Fernet key.") from exc


def ensure_can_store_secrets(*values: dict | None) -> None:
    if any(values) and _fernet() is None:
        raise MCPPolicyError("MCP_SECRET_KEY must be configured to store MCP headers or env.")


class EncryptedJSON(TypeDecorator):
    """JSON column whose value is stored as {"__enc__": <fernet token>}.

    Rows written before encryption existed (plain JSON) are still readable
    and get encrypted the next time they are saved.
    """

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if not value:
            return None
        fernet = _fernet()
        if fernet is None:
            raise MCPPolicyError("MCP_SECRET_KEY must be configured to store MCP headers or env.")
        return {_ENC_KEY: fernet.encrypt(json.dumps(value).encode()).decode()}

    def process_result_value(self, value, dialect):
        if not (isinstance(value, dict) and _ENC_KEY in value):
            return value
        fernet = _fernet()
        if fernet is None:
            raise MCPPolicyError("MCP_SECRET_KEY is missing; stored MCP secrets cannot be decrypted.")
        try:
            return json.loads(fernet.decrypt(value[_ENC_KEY].encode()))
        except InvalidToken as exc:
            raise MCPPolicyError("MCP_SECRET_KEY does not match the key used to encrypt MCP secrets.") from exc


# ===========================
#  MASKING
# ===========================
def mask(values: dict | None) -> dict | None:
    if not values:
        return values
    return {key: MASK for key in values}


def merge_masked(incoming: dict | None, existing: dict | None) -> dict | None:
    """Keep stored values for keys the client sent back still masked."""
    if not incoming:
        return incoming
    existing = existing or {}
    merged = {}
    for key, value in incoming.items():
        if value == MASK:
            if key in existing:
                merged[key] = existing[key]
            # A masked key with no stored value has nothing to keep; drop it.
        else:
            merged[key] = value
    return merged
