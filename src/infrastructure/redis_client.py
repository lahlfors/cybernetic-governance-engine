import logging
import os

import redis

from src.utils.telemetry import get_tracer

logger = logging.getLogger("Infrastructure.Redis")

class RedisWrapper:
    """
    Production-ready Redis wrapper.
    Connects to Google Cloud Memorystore via REDIS_HOST.
    Falls back to local memory ONLY if connection fails (for CI/Sandbox safety).
    """
    def __init__(self):
        self.host = os.environ.get("REDIS_HOST", "localhost")
        self.port = int(os.environ.get("REDIS_PORT", 6379))
        self.port = int(os.environ.get("REDIS_PORT", 6379))
        self.client = None
        self._local_cache = {}
        self.tracer = get_tracer()

        try:
            # Socket timeout is critical for fail-fast in sidecar architectures
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0
            )
            self.client.ping()
            logger.info(f"✅ Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Running in ephemeral mode.")
            self.client = None

    def get(self, key: str) -> str | None:
        if self.tracer:
            with self.tracer.start_as_current_span("redis.get") as span:
                span.set_attribute("redis.key", key)
                return self._do_get(key)
        return self._do_get(key)

    def _do_get(self, key: str) -> str | None:
        try:
            if self.client:
                return self.client.get(key)
        except Exception as e:
            logger.error(f"Redis read error: {e}")
        return self._local_cache.get(key)

    def set(self, key: str, value: str):
        if self.tracer:
            with self.tracer.start_as_current_span("redis.set") as span:
                span.set_attribute("redis.key", key)
                self._do_set(key, value)
        else:
             self._do_set(key, value)

    def _do_set(self, key: str, value: str):
        try:
            if self.client:
                self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis write error: {e}")
        self._local_cache[key] = value

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key)
        if val is None:
            return default
        return float(val)

# Global singleton
redis_client = RedisWrapper()
