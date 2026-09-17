"""Kite Connect client abstraction (Protocol + Mock).

This defines the boundary where a real Kite Connect client would integrate.
For assessment, we use MockKiteClient without requiring credentials.
"""

from typing import Protocol, Any
from src.broker.auth import AuthenticationError
from src.broker.rate_limit import RateLimitError
from src.broker.mock_broker import BrokerTimeout, BrokerRejected


class KiteClient(Protocol):
    """Protocol for Kite Connect client operations.
    
    A real implementation would use the official kiteconnect package.
    For assessment, MockKiteClient provides the same interface.
    """
    
    def place_order(
        self,
        tradingsymbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product: str,
        tag: str | None = None
    ) -> dict[str, Any]:
        """Place an order through Kite Connect API.
        
        Args:
            tradingsymbol: Trading symbol (e.g., "NIFTY26SEP26000CE")
            exchange: Exchange (NSE, NFO, MCX)
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, SL, SL-M
            product: MIS, NRML, CNC
            tag: Optional client order ID tag
            
        Returns:
            Order response with order_id
            
        Raises:
            AuthenticationError: Invalid or expired token
            RateLimitError: Rate limit exceeded
            BrokerTimeout: Request timeout
            BrokerRejected: Order rejected
        """
        ...
    
    def order_history(self, order_id: str) -> list[dict[str, Any]]:
        """Get order history.
        
        Args:
            order_id: Order ID to query
            
        Returns:
            List of order status updates
        """
        ...
    
    def positions(self) -> dict[str, Any]:
        """Get current positions.
        
        Returns:
            Positions data structure
        """
        ...


class MockKiteClient:
    """Mock Kite Connect client for testing without credentials.
    
    Simulates Kite API behavior including failure modes.
    """
    
    def __init__(
        self,
        fill_price: float = 25000.0,
        force_outcome: str = "success"
    ):
        """Initialize mock client.
        
        Args:
            fill_price: Price to use for fills
            force_outcome: Test outcome - "success", "timeout", "reject", 
                          "auth_error", "rate_limit"
        """
        self._fill_price = fill_price
        self._force_outcome = force_outcome
        self._orders: dict[str, dict] = {}
        self._next_order_id = 1
        self._positions: dict[str, int] = {}
        self._request_count = 0
    
    def place_order(
        self,
        tradingsymbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str,
        product: str,
        tag: str | None = None
    ) -> dict[str, Any]:
        """Mock order placement."""
        self._request_count += 1
        
        # Simulate various failure modes
        if self._force_outcome == "auth_error":
            raise AuthenticationError("Token expired or invalid")
        
        if self._force_outcome == "rate_limit":
            raise RateLimitError("Rate limit exceeded")
        
        if self._force_outcome == "timeout":
            raise BrokerTimeout(f"Order request timed out")
        
        if self._force_outcome == "reject":
            raise BrokerRejected(f"Order rejected: insufficient margin")
        
        # Success case
        order_id = str(self._next_order_id)
        self._next_order_id += 1
        
        self._orders[order_id] = {
            'order_id': order_id,
            'tag': tag,
            'tradingsymbol': tradingsymbol,
            'exchange': exchange,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'order_type': order_type,
            'product': product,
            'status': 'COMPLETE',
            'average_price': self._fill_price
        }
        
        # Update positions
        signed_qty = quantity if transaction_type == 'BUY' else -quantity
        self._positions[tradingsymbol] = self._positions.get(tradingsymbol, 0) + signed_qty
        
        return {'order_id': order_id}
    
    def order_history(self, order_id: str) -> list[dict[str, Any]]:
        """Get mock order history."""
        if order_id not in self._orders:
            return []
        
        return [self._orders[order_id]]
    
    def positions(self) -> dict[str, Any]:
        """Get mock positions."""
        return {
            'net': [
                {
                    'tradingsymbol': symbol,
                    'quantity': qty
                }
                for symbol, qty in self._positions.items()
            ]
        }
    
    def get_request_count(self) -> int:
        """Get number of requests made (for testing rate limit)."""
        return self._request_count
    
    def reset_outcome(self, outcome: str) -> None:
        """Change test outcome (for testing retry scenarios)."""
        self._force_outcome = outcome
