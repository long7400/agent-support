"""In-memory rate-limit bucket manager for delivery sender.

Implements token bucket algorithm for platform-specific rate limits:
- Telegram: 1 message/sec per chat, 20 messages/min per group, 30 messages/sec global
- Discord: (Phase 7) will use X-RateLimit headers

This is a process-local rate limiter. For multi-worker deployments,
Phase 4+ should migrate to Redis-backed rate limiting.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Attributes:
        capacity: Maximum tokens (burst size)
        refill_rate: Tokens added per second
        tokens: Current available tokens
        last_refill: Timestamp of last refill
    """

    capacity: float
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize tokens and last_refill timestamp."""
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def consume(self, count: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self._refill()
        if self.tokens >= count:
            self.tokens -= count
            return True
        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def wait_time(self, count: int = 1) -> float:
        """Calculate seconds until enough tokens are available."""
        self._refill()
        if self.tokens >= count:
            return 0.0
        deficit = count - self.tokens
        return deficit / self.refill_rate


class RateLimiter:
    """Process-local rate limiter with multiple buckets.

    Supports hierarchical rate limits (e.g., per-chat + global for Telegram).
    """

    def __init__(self) -> None:
        """Initialize rate limiter with empty bucket store."""
        self._buckets: dict[str, TokenBucket] = {}

    def get_bucket(self, key: str, capacity: float, refill_rate: float) -> TokenBucket:
        """Get or create a bucket for the given key."""
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        return self._buckets[key]

    def try_acquire(self, key: str, capacity: float, refill_rate: float, count: int = 1) -> bool:
        """Try to acquire tokens from a bucket.

        Args:
            key: Unique bucket identifier (e.g., "telegram:chat:12345")
            capacity: Bucket capacity (burst size)
            refill_rate: Tokens per second
            count: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limited
        """
        bucket = self.get_bucket(key, capacity, refill_rate)
        return bucket.consume(count)

    def wait_time(self, key: str, capacity: float, refill_rate: float, count: int = 1) -> float:
        """Calculate wait time until tokens are available."""
        bucket = self.get_bucket(key, capacity, refill_rate)
        return bucket.wait_time(count)

    def reset(self, key: str | None = None) -> None:
        """Reset one or all buckets."""
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)


# Telegram rate limit constants (from official docs)
TELEGRAM_CHAT_RATE = 1.0  # 1 message per second per chat
TELEGRAM_GROUP_RATE = 20.0 / 60.0  # 20 messages per minute per group
TELEGRAM_GLOBAL_RATE = 30.0  # 30 messages per second global


def check_telegram_rate_limits(
    chat_id: str,
    is_group: bool = False,
    limiter: RateLimiter | None = None,
) -> tuple[bool, float]:
    """Check all Telegram rate limits for a message.

    Args:
        chat_id: Telegram chat ID
        is_group: Whether the chat is a group/supergroup
        limiter: Optional shared limiter instance (creates new if None)

    Returns:
        (allowed, wait_seconds): True if allowed, else seconds to wait
    """
    if limiter is None:
        limiter = RateLimiter()

    # Check per-chat rate
    chat_key = f"telegram:chat:{chat_id}"
    if not limiter.try_acquire(chat_key, capacity=1.0, refill_rate=TELEGRAM_CHAT_RATE):
        wait = limiter.wait_time(chat_key, capacity=1.0, refill_rate=TELEGRAM_CHAT_RATE)
        return False, wait

    # Check group rate if applicable
    if is_group:
        group_key = f"telegram:group:{chat_id}"
        if not limiter.try_acquire(group_key, capacity=20.0, refill_rate=TELEGRAM_GROUP_RATE):
            wait = limiter.wait_time(group_key, capacity=20.0, refill_rate=TELEGRAM_GROUP_RATE)
            return False, wait

    # Check global rate
    global_key = "telegram:global"
    if not limiter.try_acquire(global_key, capacity=30.0, refill_rate=TELEGRAM_GLOBAL_RATE):
        wait = limiter.wait_time(global_key, capacity=30.0, refill_rate=TELEGRAM_GLOBAL_RATE)
        return False, wait

    return True, 0.0
