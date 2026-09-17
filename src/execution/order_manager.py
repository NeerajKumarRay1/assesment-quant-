"""Order management with idempotency, retry, and reconciliation."""

from dataclasses import dataclass
from datetime import datetime, UTC
from src.broker.base import Broker
from src.broker.mock_broker import BrokerTimeout, BrokerRejected, BrokerDisconnected
from src.core.order import Order, Fill, Side, OrderStatus


@dataclass
class OrderRecord:
    """Internal tracking record for an order.
    
    Maintains order state, fill details, and submission metadata
    for reconciliation and recovery.
    """
    order: Order
    status: OrderStatus
    fill: Fill | None = None
    submit_attempts: int = 0
    last_attempt_time: datetime | None = None
    rejection_reason: str | None = None


class OrderManager:
    """Manages order lifecycle with idempotency and reconciliation.
    
    Responsibilities:
    -----------------
    - Idempotent order submission (safe to retry same client_order_id)
    - State tracking (PENDING → SUBMITTED → FILLED/REJECTED)
    - Retry logic for timeouts
    - Reconciliation after network failures
    - Restart recovery support
    
    Key Guarantees:
    ---------------
    1. Same client_order_id submitted twice → same fill returned (idempotent)
    2. Timeout doesn't mean failure → order fate is UNKNOWN until reconciled
    3. All orders tracked until FILLED or REJECTED
    
    Does NOT:
    ---------
    - Make strategy decisions (Strategy's job)
    - Apply risk limits (RiskManager's job)
    - Generate signals (Indicator/Strategy's job)
    """

    def __init__(self, broker: Broker, max_retry_attempts: int = 3):
        """Initialize order manager.
        
        Args:
            broker: Broker interface for order submission
            max_retry_attempts: Maximum retries for timeout scenarios
        """
        self.broker = broker
        self.max_retry_attempts = max_retry_attempts
        
        # Track all orders by client_order_id
        self._orders: dict[str, OrderRecord] = {}

    def submit_order(
        self,
        instrument: str,
        side: Side,
        quantity: int,
        client_order_id: str | None = None
    ) -> Fill:
        """Submit order with idempotency guarantee.
        
        If order with same client_order_id was already submitted:
        - Returns existing fill if filled
        - Retries if previous attempt timed out
        - Returns same result (idempotent)
        
        Args:
            instrument: Instrument symbol
            side: BUY or SELL
            quantity: Order quantity
            client_order_id: Optional unique order ID (auto-generated if None)
            
        Returns:
            Fill object
            
        Raises:
            BrokerRejected: Order was rejected by broker
            BrokerDisconnected: Broker connection is down
            BrokerTimeout: Max retries exceeded after timeouts
        """
        # Create order object
        if client_order_id:
            order = Order(
                instrument=instrument,
                side=side,
                quantity=quantity,
                client_order_id=client_order_id
            )
        else:
            order = Order(instrument=instrument, side=side, quantity=quantity)
        
        # Check if we've seen this order before (idempotency check)
        if order.client_order_id in self._orders:
            record = self._orders[order.client_order_id]
            
            # If already filled, return existing fill
            if record.status == OrderStatus.FILLED and record.fill:
                return record.fill
            
            # If rejected, re-raise with clear message
            if record.status == OrderStatus.REJECTED:
                reason = record.rejection_reason or "Unknown reason"
                raise BrokerRejected(f"Order was previously rejected: {reason}")
            
            # If timed out, we'll retry below
        else:
            # New order - create tracking record
            record = OrderRecord(
                order=order,
                status=OrderStatus.PENDING
            )
            self._orders[order.client_order_id] = record
        
        # Attempt submission with retry logic
        for attempt in range(self.max_retry_attempts):
            record.submit_attempts += 1
            record.last_attempt_time = datetime.now(UTC)
            record.status = OrderStatus.PENDING
            
            try:
                # Submit to broker
                fill = self.broker.submit_order(order)
                
                # Success - update record
                record.status = OrderStatus.FILLED
                record.fill = fill
                return fill
                
            except BrokerTimeout:
                # Timeout - order fate is unknown
                # Mark as ACKNOWLEDGED (might have reached broker)
                record.status = OrderStatus.ACKNOWLEDGED
                
                if attempt < self.max_retry_attempts - 1:
                    # Retry (idempotent - broker handles duplicate)
                    continue
                else:
                    # Max retries exceeded
                    raise BrokerTimeout(
                        f"Order {order.client_order_id} timed out after {self.max_retry_attempts} attempts"
                    )
                    
            except BrokerRejected as e:
                # Rejected - no retry
                record.status = OrderStatus.REJECTED
                record.rejection_reason = str(e)
                raise
                
            except BrokerDisconnected:
                # Disconnected - order never sent
                record.status = OrderStatus.PENDING
                raise
        
        # Should never reach here (loop always returns or raises)
        raise RuntimeError("Unexpected control flow in submit_order")

    def get_order_status(self, client_order_id: str) -> OrderStatus:
        """Get current status of an order.
        
        Args:
            client_order_id: Order ID to query
            
        Returns:
            Current OrderStatus
            
        Raises:
            KeyError: If order ID not found
        """
        if client_order_id not in self._orders:
            raise KeyError(f"Order {client_order_id} not found")
        
        return self._orders[client_order_id].status

    def get_order_record(self, client_order_id: str) -> OrderRecord:
        """Get full order record for inspection/reconciliation.
        
        Args:
            client_order_id: Order ID to query
            
        Returns:
            OrderRecord with full details
            
        Raises:
            KeyError: If order ID not found
        """
        if client_order_id not in self._orders:
            raise KeyError(f"Order {client_order_id} not found")
        
        return self._orders[client_order_id]

    def get_pending_orders(self) -> list[OrderRecord]:
        """Get all orders that haven't been filled or rejected.
        
        Useful for:
        - Monitoring outstanding orders
        - Reconciliation after restart
        - Risk checks
        
        Returns:
            List of pending order records
        """
        return [
            record for record in self._orders.values()
            if record.status not in (OrderStatus.FILLED, OrderStatus.REJECTED)
        ]

    def get_filled_orders(self) -> list[OrderRecord]:
        """Get all successfully filled orders.
        
        Returns:
            List of filled order records
        """
        return [
            record for record in self._orders.values()
            if record.status == OrderStatus.FILLED
        ]

    def reconcile_order(self, client_order_id: str, broker_fill: Fill) -> None:
        """Reconcile local order state with broker confirmation.
        
        Called after restart or timeout when broker provides fill details.
        
        Args:
            client_order_id: Order ID to reconcile
            broker_fill: Fill details from broker
            
        Raises:
            KeyError: If order ID not found
        """
        if client_order_id not in self._orders:
            # Unknown order - create record from broker data
            # This handles restart recovery scenario
            order = Order(
                instrument=broker_fill.instrument,
                side=broker_fill.side,
                quantity=broker_fill.quantity,
                client_order_id=client_order_id
            )
            record = OrderRecord(
                order=order,
                status=OrderStatus.FILLED,
                fill=broker_fill
            )
            self._orders[client_order_id] = record
        else:
            # Update existing record
            record = self._orders[client_order_id]
            record.status = OrderStatus.FILLED
            record.fill = broker_fill

    def mark_rejected(self, client_order_id: str, reason: str) -> None:
        """Mark order as rejected (for reconciliation).
        
        Args:
            client_order_id: Order ID to mark
            reason: Rejection reason
        """
        if client_order_id not in self._orders:
            raise KeyError(f"Order {client_order_id} not found")
        
        record = self._orders[client_order_id]
        record.status = OrderStatus.REJECTED
        record.rejection_reason = reason

    def get_all_orders(self) -> dict[str, OrderRecord]:
        """Get all tracked orders (for testing/debugging).
        
        Returns:
            Dictionary mapping client_order_id to OrderRecord
        """
        return self._orders.copy()
