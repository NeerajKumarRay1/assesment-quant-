"""Transaction cost models for realistic P&L."""

from src.core.order import Fill, Side


class CostModel:
    """Base class for transaction cost calculation."""
    
    def calculate_costs(self, fill: Fill) -> float:
        """Calculate total transaction costs.
        
        Args:
            fill: Fill to calculate costs for
            
        Returns:
            Total cost amount (always positive)
        """
        raise NotImplementedError


class IndianEquityFuturesCosts(CostModel):
    """Transaction costs for Indian equity futures (NSE F&O).
    
    Components:
    - Brokerage: per trade or percentage
    - STT (Securities Transaction Tax): 0.0125% on sell side only (futures)
    - Exchange charges: ~0.002%
    - GST: 18% on brokerage + exchange charges
    - SEBI charges: negligible
    
    Simplified model focusing on brokerage and STT.
    """
    
    def __init__(
        self,
        brokerage_per_trade: float = 20.0,
        stt_rate: float = 0.000125,  # 0.0125% on sell
        exchange_charge_rate: float = 0.00002  # 0.002%
    ):
        """Initialize cost model.
        
        Args:
            brokerage_per_trade: Fixed brokerage per trade (common in India: ₹20)
            stt_rate: STT rate (0.0125% on sell side)
            exchange_charge_rate: Exchange transaction charges
        """
        self.brokerage_per_trade = brokerage_per_trade
        self.stt_rate = stt_rate
        self.exchange_charge_rate = exchange_charge_rate
        self.gst_rate = 0.18  # 18% GST
    
    def calculate_costs(self, fill: Fill) -> float:
        """Calculate total costs for a fill."""
        trade_value = fill.price * fill.quantity
        
        # Brokerage
        brokerage = self.brokerage_per_trade
        
        # Exchange charges (both sides)
        exchange_charges = trade_value * self.exchange_charge_rate
        
        # GST on brokerage + exchange charges
        gst = (brokerage + exchange_charges) * self.gst_rate
        
        # STT (only on sell side for futures)
        stt = 0.0
        if fill.side == Side.SELL:
            stt = trade_value * self.stt_rate
        
        total = brokerage + exchange_charges + gst + stt
        return total


class ZeroCosts(CostModel):
    """No transaction costs (for testing)."""
    
    def calculate_costs(self, fill: Fill) -> float:
        """Return zero costs."""
        return 0.0


class FixedCostPerTrade(CostModel):
    """Simple fixed cost per trade (for quick estimation)."""
    
    def __init__(self, cost_per_trade: float = 50.0):
        """Initialize with fixed cost.
        
        Args:
            cost_per_trade: Cost per trade in currency units
        """
        self.cost_per_trade = cost_per_trade
    
    def calculate_costs(self, fill: Fill) -> float:
        """Return fixed cost."""
        return self.cost_per_trade
