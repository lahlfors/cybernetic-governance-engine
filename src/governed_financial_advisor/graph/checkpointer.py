import os

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer(redis_url: str | None = None) -> BaseCheckpointSaver:
    """
    Returns a Redis checkpointer if explicitly configured, otherwise defaults to MemorySaver.
    """
    # 1. Determine Redis URL
    if redis_url is None:
        redis_url = os.environ.get("REDIS_URL")

    if redis_url is None:
        redis_host = os.environ.get("REDIS_HOST")
        if redis_host:
             redis_port = os.environ.get("REDIS_PORT", "6379")
             redis_url = f"redis://{redis_host}:{redis_port}"

    # 2. If no URL, default to Memory
    if not redis_url:
        print("ℹ️ No Redis configuration found (REDIS_URL/REDIS_HOST). Using MemorySaver.")
        return MemorySaver()

    # 3. Try to load Redis Saver
    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver
        # We try to import AsyncRedis just to check dependency, though AsyncRedisSaver handles it.
        # from redis.asyncio import Redis as AsyncRedis
        
        print(f"✅ Using AsyncRedisSaver at {redis_url}")
        return AsyncRedisSaver(redis_url)
    except ImportError:
         print("⚠️ langgraph-checkpoint-redis not installed. Falling back to MemorySaver.")
         return MemorySaver()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"⚠️ Redis unavailable ({e}). Falling back to MemorySaver.")
        return MemorySaver()
