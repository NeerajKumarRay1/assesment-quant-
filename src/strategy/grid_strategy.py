"""Grid trading strategy with ATR-based spacing and pyramiding."""

from dataclasses import dataclass
from src.core.position import Position


@dataclass
class GridState:
    """Tracks the state of an active grid position.
    
    Used to remember entry price and number of pyramid levels added.
    """
    entry_price: float
    pyramid_count: int  # how many times we've added to this position
    direction: int      # +1 for long, -1 for short


class GridStrategy:
    """Grid trading strategy with ATR-based dynamic spacing.
    
    Strategy Logic:
    ---------------
    ENTRY:
    - When flat and RSI < 30 (oversold) → go long 1 unit
    - When flat and RSI > 70 (overbought) → go short 1 unit
    
    PYRAMIDING:
    - If long and price rises by grid_spacing → add 1 more unit
    - If short and price falls by grid_spacing → add 1 more unit
    - Maximum pyramid_count limited by max_pyramid_levels
    
    EXIT:
    - If price moves against position by stop_loss_distance → flatten
    
    Grid spacing and stop loss are calculated as multiples of ATR.
    
    Example:
    --------
    ATR = 10, grid_multiplier = 1.5, stop_multiplier = 2.0
    
    Grid spacing = 10 × 1.5 = 15
    Stop loss = 10 × 2.0 = 20
    
    Entry at 100 (long):
    - Add pyramid at 115 (if max_pyramids allows)
    - Stop loss at 80
    """

    def __init__(
        self,
        grid_spacing_atr_multiplier: float = 1.5,
        max_pyramid_levels: int = 3,
        stop_loss_atr_multiplier: float = 2.0,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        position_size: int = 1
    ):
        """Initialize grid strategy parameters.
        
        Args:
            grid_spacing_atr_multiplier: Grid level spacing as multiple of ATR
            max_pyramid_levels: Maximum number of times to add to position
            stop_loss_atr_multiplier: Stop loss distance as multiple of ATR
            rsi_oversold: RSI threshold for long entry signal
            rsi_overbought: RSI threshold for short entry signal
            position_size: Base position size per grid level
        """
        if grid_spacing_atr_multiplier <= 0:
            raise ValueError("grid_spacing_atr_multiplier must be positive")
        if max_pyramid_levels < 1:
            raise ValueError("max_pyramid_levels must be at least 1")
        if stop_loss_atr_multiplier <= 0:
            raise ValueError("stop_loss_atr_multiplier must be positive")
        if position_size < 1:
            raise ValueError("position_size must be at least 1")
        
        self.grid_spacing_atr_multiplier = grid_spacing_atr_multiplier
        self.max_pyramid_levels = max_pyramid_levels
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.position_size = position_size
        
        # Track active grid state per instrument
        self._grid_states: dict[str, GridState] = {}

    def calculate_target_quantity(
        self,
        instrument: str,
        current_price: float,
        current_position: Position,
        atr: float,
        rsi: float | None = None
    ) -> int:
        """Calculate target position quantity based on grid logic.
        
        Args:
            instrument: Instrument symbol
            current_price: Current market price
            current_position: Current position state
            atr: Current ATR value (for spacing calculation)
            rsi: Current RSI value (for entry signals), can be None if no entry needed
            
        Returns:
            Target net position quantity (positive = long, negative = short, 0 = flat)
        """
        if instrument != current_position.instrument:
            raise ValueError(f"Instrument mismatch: {instrument} != {current_position.instrument}")
        
        current_qty = current_position.quantity
        grid_spacing = atr * self.grid_spacing_atr_multiplier
        stop_distance = atr * self.stop_loss_atr_multiplier
        
        # If we have a position, check if we should maintain/modify it
        if current_qty != 0:
            grid_state = self._grid_states.get(instrument)
            
            # If no grid state exists but we have a position, we're recovering from restart
            # Create a minimal state to at least track stops
            if grid_state is None:
                direction = 1 if current_qty > 0 else -1
                grid_state = GridState(
                    entry_price=current_position.avg_price,
                    pyramid_count=abs(current_qty) // self.position_size,
                    direction=direction
                )
                self._grid_states[instrument] = grid_state
            
            # Check stop loss
            if self._should_stop_out(current_price, grid_state.entry_price, stop_distance, grid_state.direction):
                # Exit position
                self._clear_grid_state(instrument)
                return 0
            
            # Check if we can add pyramid level
            if grid_state.pyramid_count < self.max_pyramid_levels:
                if self._should_add_pyramid(current_price, grid_state.entry_price, grid_spacing, grid_state.direction):
                    # Add one more level
                    new_qty = current_qty + (self.position_size * grid_state.direction)
                    grid_state.pyramid_count += 1
                    return new_qty
            
            # Hold current position
            return current_qty
        
        # If flat, check for entry signal
        if rsi is not None:
            if rsi < self.rsi_oversold:
                # Enter long
                self._grid_states[instrument] = GridState(
                    entry_price=current_price,
                    pyramid_count=1,
                    direction=1
                )
                return self.position_size
            elif rsi > self.rsi_overbought:
                # Enter short
                self._grid_states[instrument] = GridState(
                    entry_price=current_price,
                    pyramid_count=1,
                    direction=-1
                )
                return -self.position_size
        
        # Stay flat
        return 0

    def _should_stop_out(self, current_price: float, entry_price: float, stop_distance: float, direction: int) -> bool:
        """Check if stop loss should trigger."""
        if direction > 0:  # long position
            return current_price < (entry_price - stop_distance)
        else:  # short position
            return current_price > (entry_price + stop_distance)

    def _should_add_pyramid(self, current_price: float, entry_price: float, grid_spacing: float, direction: int) -> bool:
        """Check if price has moved favorably enough to add pyramid level."""
        if direction > 0:  # long position
            return current_price >= (entry_price + grid_spacing)
        else:  # short position
            return current_price <= (entry_price - grid_spacing)

    def _clear_grid_state(self, instrument: str) -> None:
        """Clear grid state when exiting position."""
        if instrument in self._grid_states:
            del self._grid_states[instrument]

    def reset(self) -> None:
        """Reset all grid states. Useful for testing or restarting strategy."""
        self._grid_states.clear()
