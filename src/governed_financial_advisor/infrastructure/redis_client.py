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
    Falls back to in-memory dictionary if Redis is not configured or unavailable.
    """
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.use_redis = bool(self.redis_host) and self.redis_host.lower() not in ["", "none", "false"]
        
        self.client = None
        self.memory_store = {}
        
        if self.use_redis:
            try:
                self.client = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
                # Test connection
                self.client.ping()
                logger.info(f"✅ Redis connected at {self.redis_host}:{self.redis_port}")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed ({e}). Falling back to in-memory store.")
                self.client = None
                self.use_redis = False
        else:
            logger.info("ℹ️ redis_client running in MEMORY-ONLY mode (REDIS_HOST not set).")
        
        self.tracer = get_tracer()

    def get(self, key: str) -> str | None:
        if self.use_redis and self.client:
            try:
                return self.client.get(key)
            except redis.RedisError as e:
                logger.error(f"Redis GET Error: {e}")
                return None
        return self.memory_store.get(key)

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    def set(self, key: str, value: str, ttl: int = None):
        if self.use_redis and self.client:
            try:
                self.client.set(key, value, ex=ttl)
                return
            except redis.RedisError as e:
                logger.error(f"Redis SET Error: {e}")
                # Fallback to memory if Redis fails?? No, might be split-brain. 
                # But for now we just log error if we supposedly have Redis.
                pass
        
        # In-memory implementation of TTL is not supported in this simple dict, 
        # but acceptable for simple state flags.
        self.memory_store[key] = value

    def delete(self, key: str):
        if self.use_redis and self.client:
            try:
                self.client.delete(key)
                return
            except redis.RedisError as e:
                logger.error(f"Redis DELETE Error: {e}")
                pass
        
        if key in self.memory_store:
            del self.memory_store[key]

# Global Instance
redis_client = RedisClient()
