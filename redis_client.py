import redis
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Redis enabled flag (defaults to True for normal application behavior)
_redis_enabled = os.getenv("REDIS_ENABLED", os.getenv("REDIS_BENCHMARK_ENABLED", "true")).lower() in ("true", "1", "yes")

# Use the configured Docker URL instead of assuming Redis always runs on a
# single hard-coded host/port.
redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
)

# Benchmark & telemetry metrics
_metrics = {
    "get_count": 0,
    "set_count": 0,
    "delete_count": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "get_latencies_ms": [],
    "set_latencies_ms": [],
}


def set_redis_enabled(enabled: bool):
    """Enable or disable Redis operations at runtime (for benchmarking)."""
    global _redis_enabled
    _redis_enabled = enabled


def is_redis_enabled() -> bool:
    """Return whether Redis operations are currently enabled."""
    return _redis_enabled


def reset_metrics():
    """Reset all benchmark and telemetry metrics."""
    global _metrics
    _metrics = {
        "get_count": 0,
        "set_count": 0,
        "delete_count": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "get_latencies_ms": [],
        "set_latencies_ms": [],
    }


def get_metrics() -> dict:
    """Retrieve a copy of current Redis telemetry and benchmark metrics."""
    return {
        "get_count": _metrics["get_count"],
        "set_count": _metrics["set_count"],
        "delete_count": _metrics["delete_count"],
        "cache_hits": _metrics["cache_hits"],
        "cache_misses": _metrics["cache_misses"],
        "hit_ratio": (
            (_metrics["cache_hits"] / (_metrics["cache_hits"] + _metrics["cache_misses"]) * 100)
            if (_metrics["cache_hits"] + _metrics["cache_misses"]) > 0
            else 0.0
        ),
        "get_latencies_ms": list(_metrics["get_latencies_ms"]),
        "set_latencies_ms": list(_metrics["set_latencies_ms"]),
        "avg_get_latency_ms": (
            sum(_metrics["get_latencies_ms"]) / len(_metrics["get_latencies_ms"])
            if _metrics["get_latencies_ms"]
            else 0.0
        ),
        "avg_set_latency_ms": (
            sum(_metrics["set_latencies_ms"]) / len(_metrics["set_latencies_ms"])
            if _metrics["set_latencies_ms"]
            else 0.0
        ),
    }


def get_chat_history(session_id: str):
    if not _redis_enabled:
        return []

    key = f"chat:{session_id}"
    _metrics["get_count"] += 1
    t0 = time.perf_counter()
    try:
        data = redis_client.get(key)
    finally:
        t1 = time.perf_counter()
        _metrics["get_latencies_ms"].append((t1 - t0) * 1000.0)

    if data:
        _metrics["cache_hits"] += 1
        return json.loads(data)
    _metrics["cache_misses"] += 1
    return []


def save_chat_history(session_id: str, messages: list):
    if not _redis_enabled:
        return

    key = f"chat:{session_id}"
    _metrics["set_count"] += 1
    t0 = time.perf_counter()
    try:
        redis_client.set(
            key,
            json.dumps(messages),
            ex=3600  # ⏳ expires in 1 hour
        )
    finally:
        t1 = time.perf_counter()
        _metrics["set_latencies_ms"].append((t1 - t0) * 1000.0)


def clear_chat(session_id: str):
    if not _redis_enabled:
        return

    _metrics["delete_count"] += 1
    redis_client.delete(f"chat:{session_id}")

