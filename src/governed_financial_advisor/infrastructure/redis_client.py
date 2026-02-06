import logging
import os
from typing import Dict, Optional

from src.governed_financial_advisor.utils.telemetry import get_tracer

logger = logging.getLogger("Infrastructure.Redis")

class RedisWrapper:
    """
    Ephemeral State Wrapper.
    Replaces Redis with in-memory storage as requested.
    NOTE: State is not shared across instances/restarts.
    """
    def __init__(self):
        self._local_cache: Dict[str, str] = {}
        self.tracer = get_tracer()
        logger.info("✅ Redis removed. Using In-Memory Ephemeral Storage.")

    def get(self, key: str) -> Optional[str]:
        if self.tracer:
            with self.tracer.start_as_current_span("state.get") as span:
                span.set_attribute("state.key", key)
                return self._local_cache.get(key)
        return self._local_cache.get(key)

    def set(self, key: str, value: str):
        if self.tracer:
            with self.tracer.start_as_current_span("state.set") as span:
                span.set_attribute("state.key", key)
                self._local_cache[key] = value
        else:
             self._local_cache[key] = value

    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except ValueError:
            return default

# Global singleton
redis_client = RedisWrapper()
