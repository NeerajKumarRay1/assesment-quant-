"""Order management with idempotency, retry, and reconciliation."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, UTC
from src.broker.base import Broker
from src.broker.mock_broker import BrokerTimeout, BrokerRejected, BrokerDisconnected
from src.broker.retry import RetryConfig
from src.core.order import Order, Fill, Side, OrderStatus
from src.observability.events import (
    EventLogger,
    TradingEvent,
    create_order_submitted_event,
    create_order_filled_event,
    create_order_rejected_event,
)


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
    - State tracking (PENDING → SUBMITTED → FILLED/REJECTED, or TIMEOUT)
    - Retry logic for timeouts, with exponential backoff
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

    def __init__(
        self,
        broker: Broker,
        max_retry_attempts: int = 3,
        retry_base_delay: float = 0.1,
        sleep_func: Callable[[float], None] = time.sleep,
        event_logger: EventLogger | None = None,
    ):
        """Initialize order manager.

        Args:
            broker: Broker interface for order submission
            max_retry_attempts: Maximum attempts for timeout scenarios
            retry_base_delay: First backoff delay in seconds (doubles each retry)
            sleep_func: Injectable sleep, so tests don't actually wait
            event_logger: Optional sink for ORDER_* events (e.g. StructuredLogger)
        """
        self.broker = broker
        self.max_retry_attempts = max_retry_attempts
        self._retry_config = RetryConfig(max_attempts=max_retry_attempts, base_delay=retry_base_delay)
        self._sleep = sleep_func
        self._event_logger = event_logger
        
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
            ValueError: client_order_id was already used for a different order
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

            # Reusing an id for a different order would silently return the
            # wrong fill - that's a caller bug, not a retry.
            existing = record.order
            if (existing.instrument, existing.side, existing.quantity) != (instrument, side, quantity):
                raise ValueError(
                    f"client_order_id {order.client_order_id} already used for "
                    f"{existing.side.value} {existing.quantity} {existing.instrument}"
                )
            order = existing

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
            delay = self._retry_config.calculate_delay(attempt)
            if delay > 0:
                self._sleep(delay)

            record.submit_attempts += 1
            record.last_attempt_time = datetime.now(UTC)
            record.status = OrderStatus.SUBMITTED
            self._emit(create_order_submitted_event(
                order.client_order_id, order.instrument, order.side.value, order.quantity
            ))

            try:
                # Submit to broker
                fill = self.broker.submit_order(order)

                # Success - update record
                record.status = OrderStatus.FILLED
                record.fill = fill
                self._emit(create_order_filled_event(
                    order.client_order_id, fill.instrument, fill.side.value, fill.quantity, fill.price
                ))
                return fill

            except BrokerTimeout:
                # Timeout - order fate is unknown (it may have reached the broker)
                record.status = OrderStatus.TIMEOUT

                if attempt < self.max_retry_attempts - 1:
                    # Retry after backoff (idempotent - broker handles duplicate)
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
                self._emit(create_order_rejected_event(order.client_order_id, order.instrument, str(e)))
                raise
                
            except BrokerDisconnected:
                # Disconnected - order never sent
                record.status = OrderStatus.PENDING
                raise
        
        # Should never reach here (loop always returns or raises)
        raise RuntimeError("Unexpected control flow in submit_order")

    def _emit(self, event: TradingEvent) -> None:
        if self._event_logger is not None:
            self._event_logger.log_event(event)

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
