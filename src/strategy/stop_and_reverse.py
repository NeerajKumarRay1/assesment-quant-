"""Stop-and-Reverse trading strategy - always in the market."""

from enum import Enum
from src.core.position import Position


class SARState(Enum):
    """Stop-and-Reverse position states."""
    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


class StopAndReverseStrategy:
    """Stop-and-Reverse strategy using RSI signals.
    
    Strategy Logic:
    ---------------
    Always aimed at being in the market (long or short).
    
    ENTRY (from flat):
    - RSI < oversold_threshold → go LONG
    - RSI > overbought_threshold → go SHORT
    
    REVERSAL:
    - Currently LONG and RSI > overbought_threshold → reverse to SHORT
    - Currently SHORT and RSI < oversold_threshold → reverse to LONG
    
    HOLD:
    - RSI between thresholds → maintain current position
    
    This creates a simple momentum-following system that's always exposed.
    
    Example:
    --------
    RSI goes from 25 → 75:
    
    RSI=25 (oversold) → LONG +1
    RSI=50 (neutral)  → LONG +1 (hold)
    RSI=75 (overbought) → SHORT -1 (reversed)
    """

    def __init__(
        self,
        position_size: int = 1,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0
    ):
        """Initialize Stop-and-Reverse strategy.
        
        Args:
            position_size: Size of position (always this size when positioned)
            rsi_oversold: RSI threshold for long entry/reversal signal
            rsi_overbought: RSI threshold for short entry/reversal signal
        """
        if position_size < 1:
            raise ValueError("position_size must be at least 1")
        if not (0 <= rsi_oversold <= 100):
            raise ValueError("rsi_oversold must be between 0 and 100")
        if not (0 <= rsi_overbought <= 100):
            raise ValueError("rsi_overbought must be between 0 and 100")
        if rsi_oversold >= rsi_overbought:
            raise ValueError("rsi_oversold must be less than rsi_overbought")
        
        self.position_size = position_size
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def calculate_target_quantity(
        self,
        instrument: str,
        current_position: Position,
        rsi: float
    ) -> int:
        """Calculate target position based on SAR logic.
        
        Args:
            instrument: Instrument symbol
            current_position: Current position state
            rsi: Current RSI value
            
        Returns:
            Target position: +position_size (long), -position_size (short), or 0 (flat)
        """
        if instrument != current_position.instrument:
            raise ValueError(f"Instrument mismatch: {instrument} != {current_position.instrument}")
        
        current_state = self._get_current_state(current_position.quantity)
        
        # Determine signal based on RSI
        if rsi < self.rsi_oversold:
            # Bullish signal - want to be long
            return self.position_size
        elif rsi > self.rsi_overbought:
            # Bearish signal - want to be short
            return -self.position_size
        else:
            # Neutral zone - hold current position
            return current_position.quantity

    def _get_current_state(self, quantity: int) -> SARState:
        """Determine current state from position quantity."""
        if quantity > 0:
            return SARState.LONG
        elif quantity < 0:
            return SARState.SHORT
        else:
            return SARState.FLAT

    def get_state_from_quantity(self, quantity: int) -> SARState:
        """Public method to get state from quantity (useful for testing/monitoring)."""
        return self._get_current_state(quantity)
