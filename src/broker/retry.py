"""Exponential backoff retry utility for broker operations."""

import asyncio
from typing import Callable, TypeVar, Any
from dataclasses import dataclass


T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 0.1  # seconds
    max_delay: float = 5.0   # seconds
    exponential_base: float = 2.0
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt using exponential backoff.
        
        Args:
            attempt: Attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        if attempt == 0:
            return 0.0  # No delay on first attempt
        
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        return min(delay, self.max_delay)


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry.
    
    Retryable errors are transient failures where retrying may succeed:
    - Network timeouts
    - Connection failures
    - Temporary server errors
    - Rate limit errors (with backoff)
    
    Non-retryable errors are permanent failures:
    - Invalid order parameters
    - Authentication failure (after token refresh)
    - Insufficient funds
    - Invalid instrument
    
    Args:
        error: Exception to evaluate
        
    Returns:
        True if error is retryable
    """
    from src.broker.mock_broker import BrokerTimeout, BrokerDisconnected, BrokerRejected
    
    # Retryable errors
    if isinstance(error, (BrokerTimeout, BrokerDisconnected)):
        return True
    
    # Check for rate limit error by name or message
    error_name = type(error).__name__
    if 'RateLimit' in error_name or 'rate limit' in str(error).lower():
        return True
    
    # Rejected orders are NOT retryable (permanent failure)
    if isinstance(error, BrokerRejected):
        return False
    
    # Authentication errors are NOT retryable after token refresh
    if 'Auth' in error_name or 'auth' in str(error).lower():
        return False
    
    # Default to not retryable for safety
    return False


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    config: RetryConfig | None = None,
    sleep_func: Callable[[float], Any] | None = None,
    **kwargs: Any
) -> Any:
    """Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration (uses default if None)
        sleep_func: Injectable sleep function for testing (uses asyncio.sleep if None)
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of successful function call
        
    Raises:
        Last exception if all retries exhausted
        
    Example:
        result = await retry_async(
            broker.place_order,
            order,
            config=RetryConfig(max_attempts=5)
        )
    """
    if config is None:
        config = RetryConfig()
    
    if sleep_func is None:
        sleep_func = asyncio.sleep
    
    last_error: Exception | None = None
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            # Check if error is retryable
            if not is_retryable_error(e):
                raise
            
            # Check if we have more attempts
            if attempt >= config.max_attempts - 1:
                raise
            
            # Calculate delay and wait
            delay = config.calculate_delay(attempt)
            if delay > 0:
                await sleep_func(delay)
    
    # Should never reach here, but for type safety
    if last_error:
        raise last_error
    raise RuntimeError("Retry logic error")


def retry_sync(
    func: Callable[..., T],
    *args: Any,
    config: RetryConfig | None = None,
    sleep_func: Callable[[float], None] | None = None,
    **kwargs: Any
) -> T:
    """Retry a synchronous function with exponential backoff.
    
    Args:
        func: Synchronous function to retry
        *args: Positional arguments for func
        config: Retry configuration (uses default if None)
        sleep_func: Injectable sleep function for testing (uses time.sleep if None)
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of successful function call
        
    Raises:
        Last exception if all retries exhausted
    """
    import time
    
    if config is None:
        config = RetryConfig()
    
    if sleep_func is None:
        sleep_func = time.sleep
    
    last_error: Exception | None = None
    
    for attempt in range(config.max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            # Check if error is retryable
            if not is_retryable_error(e):
                raise
            
            # Check if we have more attempts
            if attempt >= config.max_attempts - 1:
                raise
            
            # Calculate delay and wait
            delay = config.calculate_delay(attempt)
            if delay > 0:
                sleep_func(delay)
    
    # Should never reach here, but for type safety
    if last_error:
        raise last_error
    raise RuntimeError("Retry logic error")
