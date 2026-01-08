import os
from langchain_core.checkpoints.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

def get_checkpointer(redis_url: str = "redis://localhost:6379") -> BaseCheckpointSaver:
    """
    Returns a Redis checkpointer if available, otherwise falls back to MemorySaver.
    """
    try:
        from langgraph.checkpoint.redis import RedisSaver
        from redis import Redis

        # Verify connection
        redis_client = Redis.from_url(redis_url)
        # Fast check
        redis_client.ping()

        print(f"✅ Using Redis Checkpointer at {redis_url}")
        return RedisSaver(redis_client)
    except Exception as e:
        print(f"⚠️ Redis unavailable ({e}). Falling back to MemorySaver.")
        return MemorySaver()
