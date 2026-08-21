import hashlib
import json
import logging
from typing import Any

import redis

from core.config import settings

logger = logging.getLogger(__name__)

_redis = redis.from_url(settings.redis_url, decode_responses=True)

CACHE_TTL = settings.cache_ttl_seconds


def _make_key(method: str, text: str) -> str:
    """Create a cache key from method name + text hash."""
    text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"llm:{method}:{text_hash}"
def get_cached(method: str, text: str) -> dict[str, Any] | list[Any] | None:
    """Check Redis for a cached LLM response."""
    key = _make_key(method, text)
    raw = _redis.get(key)
    if raw:
        logger.info("cache hit for key: %s", key)
        return json.loads(raw)  # type: ignore[no-any-return]
    logger.info("cache miss for key: %s", key)
    return None


def set_cached(method: str, text: str, result: Any) -> None:
    """Store LLM response in Redis with TTL."""
    key = _make_key(method, text)
    logger.info("setting cache key: %s (ttl=%s)", key, CACHE_TTL)
    _redis.setex(key, CACHE_TTL, json.dumps(result))
