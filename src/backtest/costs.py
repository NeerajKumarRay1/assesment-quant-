"""Transaction cost models for realistic P&L."""

from src.core.order import Fill, Side


class CostModel:
    """Base class for transaction cost calculation."""
    
    def calculate_costs(self, fill: Fill, multiplier: int = 1) -> float:
        """Calculate total transaction costs.
        
        Args:
            fill: Fill to calculate costs for
            multiplier: Contract lot size; notional = price * quantity * multiplier
            
        Returns:
            Total cost amount (always positive)
        """
        raise NotImplementedError


class IndianEquityFuturesCosts(CostModel):
    """Transaction costs for Indian equity futures (NSE F&O).
    
    Default rates follow the NSE futures schedule effective 1 Oct 2024:
    - Brokerage: flat per order (discount broker: ₹20)
    - STT (Securities Transaction Tax): 0.02% on sell side only
    - Exchange transaction charges: 0.00173% on both sides
    - SEBI turnover fees: ₹10 per crore (0.0001%) on both sides
    - Stamp duty: 0.002% on buy side only
    - GST: 18% on brokerage + exchange charges + SEBI fees
    
    Rates change periodically; override via constructor arguments.
    """
    
    def __init__(
        self,
        brokerage_per_trade: float = 20.0,
        stt_rate: float = 0.0002,               # 0.02% on sell
        exchange_charge_rate: float = 0.0000173,  # 0.00173%
        sebi_fee_rate: float = 0.000001,        # ₹10 / crore
        stamp_duty_rate: float = 0.00002,       # 0.002% on buy
        gst_rate: float = 0.18
    ):
        """Initialize cost model.
        
        Args:
            brokerage_per_trade: Fixed brokerage per order
            stt_rate: STT rate (sell side only)
            exchange_charge_rate: Exchange transaction charges (both sides)
            sebi_fee_rate: SEBI turnover fees (both sides)
            stamp_duty_rate: Stamp duty (buy side only)
            gst_rate: GST on brokerage + exchange + SEBI charges
        """
        self.brokerage_per_trade = brokerage_per_trade
        self.stt_rate = stt_rate
        self.exchange_charge_rate = exchange_charge_rate
        self.sebi_fee_rate = sebi_fee_rate
        self.stamp_duty_rate = stamp_duty_rate
        self.gst_rate = gst_rate
    
    def calculate_costs(self, fill: Fill, multiplier: int = 1) -> float:
        """Calculate total costs for a fill."""
        trade_value = fill.price * fill.quantity * multiplier
        
        brokerage = self.brokerage_per_trade
        exchange_charges = trade_value * self.exchange_charge_rate
        sebi_fees = trade_value * self.sebi_fee_rate
        gst = (brokerage + exchange_charges + sebi_fees) * self.gst_rate
        
        stt = trade_value * self.stt_rate if fill.side == Side.SELL else 0.0
        stamp_duty = trade_value * self.stamp_duty_rate if fill.side == Side.BUY else 0.0
        
        return brokerage + exchange_charges + sebi_fees + gst + stt + stamp_duty


class ZeroCosts(CostModel):
    """No transaction costs (for testing)."""
    
    def calculate_costs(self, fill: Fill, multiplier: int = 1) -> float:
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
    
    def calculate_costs(self, fill: Fill, multiplier: int = 1) -> float:
        """Return fixed cost."""
        return self.cost_per_trade
