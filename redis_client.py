import redis
import json

# Connect to Redis (Docker running on localhost:6379)
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)


def get_chat_history(session_id: str):
    key = f"chat:{session_id}"
    data = redis_client.get(key)

    if data:
        return json.loads(data)
    return []


def save_chat_history(session_id: str, messages: list):
    key = f"chat:{session_id}"

    redis_client.set(
        key,
        json.dumps(messages),
        ex=3600  # ⏳ expires in 1 hour
    )


def clear_chat(session_id: str):
    redis_client.delete(f"chat:{session_id}")