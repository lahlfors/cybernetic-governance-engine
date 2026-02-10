import logging
import os
import redis
from opentelemetry import trace
from src.governed_financial_advisor.utils.telemetry import get_tracer

logger = logging.getLogger("Infrastructure.Redis")

class RedisClient:
    """
    Wrapper around Redis for state management.
    Handles connection pooling and provides typed accessors.
    """
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.tracer = get_tracer()

    def get(self, key: str) -> str | None:
        try:
            return self.client.get(key)
        except redis.RedisError as e:
            logger.error(f"Redis GET Error: {e}")
            return None

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    def set(self, key: str, value: str, ttl: int = None):
        try:
            self.client.set(key, value, ex=ttl)
        except redis.RedisError as e:
            logger.error(f"Redis SET Error: {e}")

    def delete(self, key: str):
        try:
            self.client.delete(key)
        except redis.RedisError as e:
            logger.error(f"Redis DELETE Error: {e}")

# Global Instance
redis_client = RedisClient()
