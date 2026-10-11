import logging
import time

import redis

from app.core.config import get_settings
from app.core.exceptions import RateLimitedError
from app.core.redis import get_redis

log = logging.getLogger(__name__)


def enforce_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    """Fixed-window counter in Redis. Fails OPEN if Redis is down (availability over strictness)."""
    s = get_settings()
    if not s.RATE_LIMIT_ENABLED:
        return
    bucket = int(time.time() // window_seconds)
    rkey = f"rl:{key}:{bucket}"
    try:
        r = get_redis()
        count = r.incr(rkey)
        if count == 1:
            r.expire(rkey, window_seconds + 10)
    except redis.RedisError:
        log.warning("rate limiter unavailable (redis)")
        return
    if count > limit:
        retry = window_seconds - int(time.time()) % window_seconds
        raise RateLimitedError("Too many requests. Please slow down.", headers={"Retry-After": str(retry)})
