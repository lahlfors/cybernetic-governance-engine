import os

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer(redis_url: str | None = None) -> BaseCheckpointSaver:
    """
    Returns a Redis checkpointer if available, otherwise falls back to MemorySaver.
    """
    try:
        from langgraph.checkpoint.redis import RedisSaver
        from redis import Redis

        # Build redis_url from environment if not provided
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"

        # Verify connection with a ping test
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
        redis_client.close()

        print(f"✅ Using Redis Checkpointer at {redis_url}")
        # RedisSaver expects the URL string, not a Redis client
        return RedisSaver(redis_url)
    except Exception as e:
        print(f"⚠️ Redis unavailable ({e}). Falling back to MemorySaver.")
        return MemorySaver()
