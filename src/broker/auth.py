"""Authentication and token management abstraction."""

from typing import Protocol
from datetime import datetime, UTC


class TokenProvider(Protocol):
    """Protocol for authentication token management.
    
    Implementations should:
    - Store tokens securely (not in logs)
    - Refresh tokens before expiry
    - Handle refresh failures gracefully
    """
    
    def get_token(self) -> str:
        """Get current valid token.
        
        Returns:
            Valid authentication token
            
        Raises:
            AuthenticationError: If token is invalid and refresh fails
        """
        ...
    
    def refresh_token(self) -> str:
        """Refresh authentication token.
        
        Returns:
            New valid token
            
        Raises:
            AuthenticationError: If refresh fails
        """
        ...


class AuthenticationError(Exception):
    """Authentication or token refresh failed."""
    pass


class MockTokenProvider:
    """Mock token provider for testing.
    
    Simulates token expiry and refresh behavior without real credentials.
    """
    
    def __init__(
        self,
        initial_token: str = "mock_token_123",
        should_fail_refresh: bool = False,
        expire_after_calls: int | None = None
    ):
        """Initialize mock token provider.
        
        Args:
            initial_token: Initial token value
            should_fail_refresh: If True, refresh_token() raises AuthenticationError
            expire_after_calls: Token expires after N get_token() calls (simulates expiry)
        """
        self._current_token = initial_token
        self._should_fail_refresh = should_fail_refresh
        self._expire_after_calls = expire_after_calls
        self._call_count = 0
        self._refresh_count = 0
        self._is_expired = False
    
    def get_token(self) -> str:
        """Get current token.
        
        Returns:
            Current token
            
        Raises:
            AuthenticationError: If token is expired and not refreshed
        """
        if self._is_expired:
            raise AuthenticationError("Token expired")
        
        self._call_count += 1
        
        # Simulate expiry after configured calls
        if self._expire_after_calls and self._call_count >= self._expire_after_calls:
            self._is_expired = True
        
        return self._current_token
    
    def refresh_token(self) -> str:
        """Refresh token.
        
        Returns:
            New token
            
        Raises:
            AuthenticationError: If refresh is configured to fail
        """
        if self._should_fail_refresh:
            raise AuthenticationError("Token refresh failed")
        
        self._refresh_count += 1
        self._current_token = f"mock_token_refreshed_{self._refresh_count}"
        self._is_expired = False
        self._call_count = 0
        
        return self._current_token
    
    def get_refresh_count(self) -> int:
        """Get number of times token was refreshed (for testing)."""
        return self._refresh_count
    
    def expire_token(self) -> None:
        """Force token to expire (for testing)."""
        self._is_expired = True


class TokenRefreshHandler:
    """Wrapper that automatically refreshes tokens on auth failures.
    
    Usage:
        handler = TokenRefreshHandler(token_provider)
        
        # Will auto-refresh if token expired
        token = handler.get_token_with_refresh()
    """
    
    def __init__(self, provider: TokenProvider):
        """Initialize handler.
        
        Args:
            provider: Token provider to wrap
        """
        self._provider = provider
    
    def get_token_with_refresh(self) -> str:
        """Get token, refreshing if expired.
        
        Returns:
            Valid token
            
        Raises:
            AuthenticationError: If refresh fails
        """
        try:
            return self._provider.get_token()
        except AuthenticationError:
            # Token expired, try to refresh
            return self._provider.refresh_token()
