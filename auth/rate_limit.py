"""Slow down password guessing: limit failed logins per email and per IP.

Counters live in Redis so they survive restarts and work across workers.
If Redis is down, logins are allowed (fail open) rather than locking
everyone out.
"""

import logging

logger = logging.getLogger("aroma.auth")

MAX_FAILURES_PER_EMAIL = 5
MAX_FAILURES_PER_IP = 20
WINDOW_SECONDS = 15 * 60


def _keys(email: str, ip: str) -> list[tuple[str, int]]:
    return [(f"auth:fail:email:{email}", MAX_FAILURES_PER_EMAIL), (f"auth:fail:ip:{ip}", MAX_FAILURES_PER_IP)]


def is_blocked(email: str, ip: str) -> bool:
    try:
        from redis_client import redis_client
        return any(int(redis_client.get(key) or 0) >= limit for key, limit in _keys(email, ip))
    except Exception as exc:
        logger.warning("Login rate limit check skipped: %s", exc)
        return False


def record_failure(email: str, ip: str) -> None:
    try:
        from redis_client import redis_client
        pipe = redis_client.pipeline()
        for key, _ in _keys(email, ip):
            pipe.incr(key)
            pipe.expire(key, WINDOW_SECONDS, nx=True)
        pipe.execute()
    except Exception as exc:
        logger.warning("Could not record failed login: %s", exc)


def clear_failures(email: str) -> None:
    try:
        from redis_client import redis_client
        redis_client.delete(f"auth:fail:email:{email}")
    except Exception as exc:
        logger.warning("Could not clear failed logins: %s", exc)
