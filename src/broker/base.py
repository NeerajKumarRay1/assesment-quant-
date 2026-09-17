from abc import ABC, abstractmethod
from src.core.order import Order, Fill, OrderStatus


class Broker(ABC):
    """Abstraction every broker adapter (mock or real) must satisfy.

    Strategy, Risk, and OrderManager code depend ONLY on this interface,
    never on a concrete broker. This is the dependency-inversion seam that
    lets us swap MockBroker for a future ZerodhaBroker without touching
    any trading logic.
    """

    @abstractmethod
    def submit_order(self, order: Order) -> Fill:
        """Submit an order and return the resulting Fill.

        Happy path only for now - failure modes (rejects, timeouts,
        disconnects) are added in the next pass via exceptions.
        """
        raise NotImplementedError
    
    # Optional query methods for reconciliation (Phase 4)
    # Implementations can return None if not supported
    
    def get_order(self, client_order_id: str) -> tuple[OrderStatus, Fill | None] | None:
        """Query order status from broker.
        
        Args:
            client_order_id: Order ID to query
            
        Returns:
            Tuple of (status, fill) or None if not supported
        """
        return None
    
    def get_positions(self) -> dict[str, int] | None:
        """Get current positions from broker.
        
        Returns:
            Dictionary mapping instrument to net quantity, or None if not supported
        """
        return None
    
    def get_pnl(self) -> float | None:
        """Get current P&L from broker.
        
        Returns:
            Current P&L or None if not supported
        """
        return None