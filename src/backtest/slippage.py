"""Slippage models for realistic backtest fills."""

from src.core.order import Side


class SlippageModel:
    """Base class for slippage calculation.
    
    Slippage represents the difference between expected price and actual fill price
    due to market impact, latency, and order execution mechanics.
    """
    
    def calculate_slippage(self, side: Side, price: float, quantity: int) -> float:
        """Calculate slippage amount to add to price.
        
        Args:
            side: BUY or SELL
            price: Base price (typically bar open)
            quantity: Order size
            
        Returns:
            Slippage amount (positive = worse fill)
            
        Note: Slippage is ALWAYS unfavorable:
            - BUY: pay MORE (slippage > 0)
            - SELL: receive LESS (slippage > 0, but subtracts from price)
        """
        raise NotImplementedError


class FixedPercentageSlippage(SlippageModel):
    """Simple slippage model: fixed percentage of price.
    
    Example:
        price = 100, slippage_pct = 0.001 (0.1%)
        BUY → fill at 100.10
        SELL → fill at 99.90
    """
    
    def __init__(self, slippage_pct: float = 0.001):
        """Initialize with slippage percentage.
        
        Args:
            slippage_pct: Slippage as decimal (0.001 = 0.1%)
        """
        if slippage_pct < 0:
            raise ValueError("slippage_pct must be non-negative")
        self.slippage_pct = slippage_pct
    
    def calculate_slippage(self, side: Side, price: float, quantity: int) -> float:
        """Calculate fixed percentage slippage."""
        return price * self.slippage_pct


class ZeroSlippage(SlippageModel):
    """No slippage (for testing or ultra-liquid markets)."""
    
    def calculate_slippage(self, side: Side, price: float, quantity: int) -> float:
        """Return zero slippage."""
        return 0.0
