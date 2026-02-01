import os

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer(redis_url: str | None = None) -> BaseCheckpointSaver:
    """
    Returns a Redis checkpointer if available, otherwise falls back to MemorySaver.
    """
    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver
        from redis.asyncio import Redis as AsyncRedis
        print("DEBUG: Loaded checkpointer.py VERSION 2")

        # Build redis_url from environment if not provided
        if redis_url is None:
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = os.environ.get("REDIS_PORT", "6379")
            redis_url = f"redis://{redis_host}:{redis_port}"

        # We assume the caller handles the connection lifecycle or we let garbage collection handle it.
        # Ideally, we should close, but for a global checkpointer in a long-running app, it's fine.
        
        print(f"✅ Using AsyncRedisSaver at {redis_url}")
        return AsyncRedisSaver(redis_url)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"⚠️ Redis unavailable ({e}). Falling back to MemorySaver.")
        return MemorySaver()
