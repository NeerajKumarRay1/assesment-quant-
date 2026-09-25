"""Risk management layer for position sizing and exposure controls."""

from dataclasses import dataclass
from src.core.position import Position
from src.observability.events import EventLogger, create_risk_rejected_event


@dataclass(frozen=True)
class RiskDecision:
    """Result of risk evaluation.
    
    Represents what the risk layer allows after checking constraints.
    Immutable by design - a risk decision is a fact about what was allowed
    at a point in time.
    """
    allowed: bool                    # Can we proceed with any trading action?
    target_quantity: int            # What net position quantity is allowed?
    rejection_reason: str | None    # Why was it blocked/reduced? None if allowed as-is.


class RiskManager:
    """Enforces position limits and kill switch for risk control.
    
    Responsibilities:
    - Enforce maximum position caps (long and short)
    - Implement kill switch to block new exposure
    - Allow position reduction even when kill switch is active
    
    Does NOT:
    - Create orders
    - Track positions (receives Position from caller)
    - Make trading decisions
    """

    def __init__(
        self,
        max_position: int,
        kill_switch: bool = False,
        event_logger: "EventLogger | None" = None,
    ):
        """Initialize risk manager.
        
        Args:
            max_position: Maximum allowed net position (positive for long, negative for short).
                         Example: max_position=5 allows +5 long or -5 short.
            kill_switch: If True, blocks all new exposure but allows reducing positions.
            event_logger: Optional sink for RISK_REJECTED events (e.g. StructuredLogger).
        """
        if max_position <= 0:
            raise ValueError("max_position must be positive")
        
        self.max_position = max_position
        self.kill_switch = kill_switch
        self._event_logger = event_logger

    def evaluate(
        self,
        instrument: str,
        desired_quantity: int,
        current_position: Position,
        circuit_breaker_active: bool = False
    ) -> RiskDecision:
        """Evaluate if desired quantity is allowed under current risk constraints.
        
        Args:
            instrument: Instrument symbol (must match current_position.instrument)
            desired_quantity: Target net position the strategy wants
            current_position: Current position state
            circuit_breaker_active: If True, blocks risk-increasing positions (from macro regime)
            
        Returns:
            RiskDecision with allowed flag, actual target quantity, and rejection reason
            
        Examples:
            current=0, desired=+7, cap=+5 → allowed=True, target=+5 (capped)
            current=+5, desired=+7, cap=+5 → allowed=True, target=+5 (no increase)
            current=0, desired=+3, kill_switch=True → allowed=False (blocked)
            current=+5, desired=0, kill_switch=True → allowed=True (reduction OK)
            current=0, desired=+3, circuit_breaker=True → allowed=False (blocked by macro)
            current=+5, desired=+3, circuit_breaker=True → allowed=True (reduction OK)
            current=+5, desired=-5, kill_switch=True → allowed=True, target=0 (flip blocked, flatten only)
        """
        if instrument != current_position.instrument:
            return RiskDecision(
                allowed=False,
                target_quantity=current_position.quantity,
                rejection_reason=f"Instrument mismatch: {instrument} != {current_position.instrument}"
            )

        current_qty = current_position.quantity

        # Circuit breaker (from macro regime) and kill switch share the same rule:
        # block new or increased exposure, allow reduction.
        for active, label in (
            (circuit_breaker_active, "Circuit breaker active (macro regime)"),
            (self.kill_switch, "Kill switch active"),
        ):
            if active:
                decision = self._restrict_to_reduction(current_qty, desired_quantity, label)
                if decision is not None:
                    self._emit_rejection(instrument, desired_quantity, decision)
                    return decision

        # Apply position cap
        capped_quantity = self._apply_position_cap(desired_quantity)

        # If we had to cap it, note that in the decision
        was_capped = capped_quantity != desired_quantity

        return RiskDecision(
            allowed=True,
            target_quantity=capped_quantity,
            rejection_reason=f"Position capped from {desired_quantity} to {capped_quantity}" if was_capped else None
        )

    @staticmethod
    def _restrict_to_reduction(current_qty: int, desired_quantity: int, label: str) -> RiskDecision | None:
        """Allow only exposure-reducing moves. Returns None if desired move is a pure reduction.

        A flip through zero (e.g. +5 -> -3) is NOT a reduction: it opens new exposure
        on the other side. The closing leg is still allowed, so the target becomes flat.
        """
        is_flip = current_qty != 0 and desired_quantity != 0 and (current_qty > 0) != (desired_quantity > 0)
        if is_flip:
            return RiskDecision(
                allowed=True,
                target_quantity=0,
                rejection_reason=f"{label}: reversal blocked, flattening only",
            )
        if abs(desired_quantity) > abs(current_qty):
            return RiskDecision(
                allowed=False,
                target_quantity=current_qty,
                rejection_reason=f"{label}: no new or increased exposure allowed",
            )
        return None

    def _emit_rejection(self, instrument: str, desired_quantity: int, decision: RiskDecision) -> None:
        if self._event_logger is not None and decision.rejection_reason:
            self._event_logger.log_event(
                create_risk_rejected_event(instrument, desired_quantity, decision.rejection_reason)
            )

    def _apply_position_cap(self, desired_quantity: int) -> int:
        """Apply position cap constraints.
        
        Cap is symmetric: +max_position for long, -max_position for short.
        
        Args:
            desired_quantity: Target position
            
        Returns:
            Position capped to allowed range [-max_position, +max_position]
        """
        if desired_quantity > self.max_position:
            return self.max_position
        elif desired_quantity < -self.max_position:
            return -self.max_position
        else:
            return desired_quantity
