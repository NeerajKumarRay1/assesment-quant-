"""Rate limiting for broker API requests."""

import time
from dataclasses import dataclass


class RateLimitError(Exception):
    """Request rejected due to rate limit."""
    pass


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: float = 10.0
    
    @property
    def min_interval(self) -> float:
        """Minimum interval between requests in seconds."""
        return 1.0 / self.requests_per_second


class RateLimiter:
    """Token bucket rate limiter.
    
    Limits requests to a maximum rate. Suitable for broker API rate limits.
    Uses a simple minimum-interval approach for simplicity.
    """
    
    def __init__(
        self,
        config: RateLimitConfig | None = None,
        time_func: callable = None
    ):
        """Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
            time_func: Injectable time function for testing (uses time.time if None)
        """
        self._config = config or RateLimitConfig()
        self._time_func = time_func or time.time
        self._last_request_time: float | None = None
    
    def acquire(self, block: bool = True) -> bool:
        """Acquire permission to make a request.
        
        Args:
            block: If True, waits until request is allowed. If False, returns immediately.
            
        Returns:
            True if request allowed, False if rate limited (only when block=False)
            
        Raises:
            RateLimitError: If block=False and rate limit exceeded
        """
        current_time = self._time_func()
        
        if self._last_request_time is None:
            # First request
            self._last_request_time = current_time
            return True
        
        elapsed = current_time - self._last_request_time
        min_interval = self._config.min_interval
        
        if elapsed >= min_interval:
            # Enough time has passed
            self._last_request_time = current_time
            return True
        
        if not block:
            # Non-blocking mode - reject immediately
            raise RateLimitError(
                f"Rate limit exceeded: {self._config.requests_per_second} requests/sec"
            )
        
        # Blocking mode - wait for required interval
        wait_time = min_interval - elapsed
        time.sleep(wait_time)
        self._last_request_time = self._time_func()
        return True
    
    def reset(self) -> None:
        """Reset rate limiter (for testing)."""
        self._last_request_time = None


class AsyncRateLimiter:
    """Async version of rate limiter for async broker operations."""
    
    def __init__(
        self,
        config: RateLimitConfig | None = None,
        time_func: callable = None
    ):
        """Initialize async rate limiter.
        
        Args:
            config: Rate limit configuration
            time_func: Injectable time function for testing
        """
        self._config = config or RateLimitConfig()
        self._time_func = time_func or time.time
        self._last_request_time: float | None = None
    
    async def acquire(self, block: bool = True) -> bool:
        """Acquire permission to make a request (async).
        
        Args:
            block: If True, waits until request is allowed
            
        Returns:
            True if request allowed
            
        Raises:
            RateLimitError: If block=False and rate limit exceeded
        """
        import asyncio
        
        current_time = self._time_func()
        
        if self._last_request_time is None:
            self._last_request_time = current_time
            return True
        
        elapsed = current_time - self._last_request_time
        min_interval = self._config.min_interval
        
        if elapsed >= min_interval:
            self._last_request_time = current_time
            return True
        
        if not block:
            raise RateLimitError(
                f"Rate limit exceeded: {self._config.requests_per_second} requests/sec"
            )
        
        # Wait for required interval
        wait_time = min_interval - elapsed
        await asyncio.sleep(wait_time)
        self._last_request_time = self._time_func()
        return True
    
    def reset(self) -> None:
        """Reset rate limiter (for testing)."""
        self._last_request_time = None
