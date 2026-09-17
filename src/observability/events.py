"""Trading event model for observability."""

from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from enum import Enum
from typing import Any


class EventType(Enum):
    """Types of observable trading events."""
    
    # Order lifecycle
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    
    # Position events
    POSITION_CHANGED = "POSITION_CHANGED"
    
    # Risk events
    RISK_REJECTED = "RISK_REJECTED"
    
    # Macro regime events
    CIRCUIT_BREAKER_TRIGGERED = "CIRCUIT_BREAKER_TRIGGERED"
    REGIME_CHANGED = "REGIME_CHANGED"
    
    # Contract lifecycle
    ROLLOVER_REQUIRED = "ROLLOVER_REQUIRED"
    ROLLOVER_COMPLETED = "ROLLOVER_COMPLETED"
    
    # Reconciliation
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"
    
    # Engine lifecycle
    ENGINE_STARTED = "ENGINE_STARTED"
    ENGINE_STOPPED = "ENGINE_STOPPED"
    ENGINE_ERROR = "ENGINE_ERROR"


@dataclass
class TradingEvent:
    """A single observable trading event.
    
    Flexible event model with required core fields and optional metadata.
    All events use this same structure for consistency.
    """
    timestamp: datetime
    event_type: EventType
    message: str
    
    # Optional trading-specific fields
    instrument: str | None = None
    order_id: str | None = None
    client_order_id: str | None = None
    
    # Flexible metadata for event-specific details
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation with proper timestamp formatting
        """
        result = asdict(self)
        
        # Format timestamp as ISO string
        result['timestamp'] = self.timestamp.isoformat()
        
        # Convert EventType enum to string
        result['event_type'] = self.event_type.value
        
        return result


def create_order_submitted_event(
    client_order_id: str,
    instrument: str,
    side: str,
    quantity: int
) -> TradingEvent:
    """Create ORDER_SUBMITTED event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.ORDER_SUBMITTED,
        message=f"Order submitted: {side} {quantity} {instrument}",
        instrument=instrument,
        client_order_id=client_order_id,
        metadata={
            "side": side,
            "quantity": quantity
        }
    )


def create_order_filled_event(
    order_id: str,
    instrument: str,
    side: str,
    quantity: int,
    price: float
) -> TradingEvent:
    """Create ORDER_FILLED event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.ORDER_FILLED,
        message=f"Order filled: {side} {quantity} {instrument} @ {price}",
        instrument=instrument,
        order_id=order_id,
        metadata={
            "side": side,
            "quantity": quantity,
            "price": price
        }
    )


def create_order_rejected_event(
    client_order_id: str,
    instrument: str,
    reason: str
) -> TradingEvent:
    """Create ORDER_REJECTED event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.ORDER_REJECTED,
        message=f"Order rejected: {instrument} - {reason}",
        instrument=instrument,
        client_order_id=client_order_id,
        metadata={"reason": reason}
    )


def create_position_changed_event(
    instrument: str,
    old_quantity: int,
    new_quantity: int,
    realized_pnl: float
) -> TradingEvent:
    """Create POSITION_CHANGED event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.POSITION_CHANGED,
        message=f"Position changed: {instrument} {old_quantity} → {new_quantity}",
        instrument=instrument,
        metadata={
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
            "realized_pnl": realized_pnl
        }
    )


def create_risk_rejected_event(
    instrument: str,
    desired_quantity: int,
    reason: str
) -> TradingEvent:
    """Create RISK_REJECTED event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.RISK_REJECTED,
        message=f"Risk rejected: {instrument} - {reason}",
        instrument=instrument,
        metadata={
            "desired_quantity": desired_quantity,
            "reason": reason
        }
    )


def create_circuit_breaker_event(reason: str) -> TradingEvent:
    """Create CIRCUIT_BREAKER_TRIGGERED event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.CIRCUIT_BREAKER_TRIGGERED,
        message=f"Circuit breaker triggered: {reason}",
        metadata={"reason": reason}
    )


def create_reconciliation_mismatch_event(
    instrument: str,
    expected: int | float,
    actual: int | float,
    mismatch_type: str
) -> TradingEvent:
    """Create RECONCILIATION_MISMATCH event."""
    return TradingEvent(
        timestamp=datetime.now(UTC),
        event_type=EventType.RECONCILIATION_MISMATCH,
        message=f"Reconciliation mismatch: {instrument} {mismatch_type}",
        instrument=instrument,
        metadata={
            "mismatch_type": mismatch_type,
            "expected": expected,
            "actual": actual,
            "difference": actual - expected
        }
    )
