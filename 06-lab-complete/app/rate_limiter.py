"""Redis-backed sliding window shared by all agent workers."""

from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_MS = 60_000

# Use Redis time and make pruning, counting and admitting a request atomic.
take_slot = r.register_script(
    """
    local clock = redis.call('TIME')
    local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
    local limit = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])

    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
    if redis.call('ZCARD', KEYS[1]) >= limit then
        local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
        return math.ceil((tonumber(oldest[2]) + window - now) / 1000)
    end

    redis.call('ZADD', KEYS[1], now, ARGV[3])
    redis.call('PEXPIRE', KEYS[1], window)
    return 0
    """
)


def check_rate_limit(key: str) -> None:
    key_digest = sha256(key.encode()).hexdigest()
    retry_after = take_slot(
        keys=[f"agent:{settings.environment}:rate:{key_digest}"],
        args=[settings.rate_limit_per_minute, WINDOW_MS, uuid4().hex],
    )
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
