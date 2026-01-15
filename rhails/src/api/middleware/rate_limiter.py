"""Rate limiting middleware to prevent abuse."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Simple in-memory rate limiter.

    Implements token bucket algorithm for rate limiting API requests.
    For production, consider using Redis-based rate limiting.
    """

    def __init__(
        self,
        requests_per_minute: int = 10,
        burst_size: int = 5,
        cleanup_interval: int = 60,
    ):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per user
            burst_size: Maximum burst requests allowed
            cleanup_interval: Interval (seconds) to cleanup old entries
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.cleanup_interval = cleanup_interval

        # Store: user_id -> (tokens, last_update, request_count)
        self.buckets: dict[str, tuple[float, float, int]] = defaultdict(
            lambda: (burst_size, time.time(), 0)
        )
        self.last_cleanup = time.time()

    def _refill_tokens(self, user_id: str) -> float:
        """Refill tokens for user based on time elapsed.

        Args:
            user_id: User identifier

        Returns:
            Current token count
        """
        tokens, last_update, count = self.buckets[user_id]
        current_time = time.time()

        # Calculate tokens to add based on time elapsed
        time_elapsed = current_time - last_update
        tokens_to_add = time_elapsed * (self.requests_per_minute / 60.0)

        # Add tokens but don't exceed burst size
        new_tokens = min(tokens + tokens_to_add, self.burst_size)

        # Update bucket
        self.buckets[user_id] = (new_tokens, current_time, count)

        return new_tokens

    async def check_rate_limit(self, user_id: str) -> None:
        """Check if user has exceeded rate limit.

        Args:
            user_id: User identifier

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Periodic cleanup
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries()
            self.last_cleanup = current_time

        # Refill tokens
        tokens = self._refill_tokens(user_id)

        # Check if user has tokens available
        if tokens < 1.0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.requests_per_minute} requests per minute allowed",
                    "retry_after": int(60 / self.requests_per_minute),
                },
                headers={"Retry-After": str(int(60 / self.requests_per_minute))},
            )

        # Consume one token
        tokens, last_update, count = self.buckets[user_id]
        self.buckets[user_id] = (tokens - 1.0, last_update, count + 1)

    def _cleanup_old_entries(self) -> None:
        """Clean up old entries to prevent memory growth."""
        current_time = time.time()
        cutoff_time = current_time - (self.cleanup_interval * 2)

        # Remove entries not accessed recently
        to_remove = [
            user_id
            for user_id, (_, last_update, _) in self.buckets.items()
            if last_update < cutoff_time
        ]

        for user_id in to_remove:
            del self.buckets[user_id]

    def get_user_stats(self, user_id: str) -> dict:
        """Get rate limit statistics for user.

        Args:
            user_id: User identifier

        Returns:
            Dict with tokens available, total requests, etc.
        """
        if user_id not in self.buckets:
            return {
                "tokens_available": self.burst_size,
                "requests_remaining": self.burst_size,
                "total_requests": 0,
            }

        tokens = self._refill_tokens(user_id)
        _, _, count = self.buckets[user_id]

        return {
            "tokens_available": int(tokens),
            "requests_remaining": int(tokens),
            "total_requests": count,
            "limit_per_minute": self.requests_per_minute,
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(request: Request) -> None:
    """FastAPI dependency for rate limiting.

    Args:
        request: FastAPI request

    Example:
        @app.get("/api/resource", dependencies=[Depends(check_rate_limit)])
        async def get_resource():
            return {"data": "value"}
    """
    # Extract user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)

    if not user_id:
        # Use IP address as fallback for unauthenticated requests
        user_id = request.client.host if request.client else "unknown"

    await rate_limiter.check_rate_limit(user_id)
