"""Backtest engine for historical strategy simulation."""

from dataclasses import dataclass, field
from src.core.bar import Bar
from src.core.order import Order, Fill, Side
from src.core.position import Position
from src.backtest.slippage import SlippageModel, ZeroSlippage
from src.backtest.costs import CostModel, ZeroCosts
from src.risk.risk_manager import RiskManager


@dataclass
class BacktestResult:
    """Results from a backtest run.
    
    Contains full trade history, P&L breakdown, and performance metrics.
    """
    instrument: str
    fills: list[Fill] = field(default_factory=list)
    final_position: Position | None = None
    gross_pnl: float = 0.0
    transaction_costs: float = 0.0
    slippage_costs: float = 0.0
    net_pnl: float = 0.0
    returns_pct: float = 0.0
    equity_curve: list[float] = field(default_factory=list)
    total_trades: int = 0
    
    def summary(self) -> str:
        """Return human-readable summary."""
        return f"""
Backtest Results for {self.instrument}
{'='*50}
Total Trades:        {self.total_trades}
Gross P&L:          {self.gross_pnl:,.2f}
Transaction Costs:  {self.transaction_costs:,.2f}
Slippage Costs:     {self.slippage_costs:,.2f}
Net P&L:            {self.net_pnl:,.2f}
Returns:            {self.returns_pct:.2f}%
Final Position:     {self.final_position.quantity if self.final_position else 0}
{'='*50}
"""


class BacktestEngine:
    """Historical backtest engine with bar-accurate execution.
    
    Key Features:
    -------------
    1. Bar-accurate fills: signal at bar[t] close → fill at bar[t+1] open
    2. Slippage modeling: realistic fill prices
    3. Transaction costs: brokerage, taxes, fees
    4. No lookahead: only uses data available up to current time
    5. Risk integration: respects position caps and kill switch
    
    Usage:
    ------
    engine = BacktestEngine(
        slippage_model=FixedPercentageSlippage(0.001),
        cost_model=IndianEquityFuturesCosts()
    )
    
    result = engine.run(
        bars=historical_data,
        strategy_signals=signal_generator,
        risk_manager=risk_mgr,
        initial_capital=100000
    )
    """
    
    def __init__(
        self,
        slippage_model: SlippageModel | None = None,
        cost_model: CostModel | None = None
    ):
        """Initialize backtest engine.
        
        Args:
            slippage_model: Model for calculating slippage (default: ZeroSlippage)
            cost_model: Model for calculating costs (default: ZeroCosts)
        """
        self.slippage_model = slippage_model or ZeroSlippage()
        self.cost_model = cost_model or ZeroCosts()
    
    def run_simple(
        self,
        bars: list[Bar],
        target_quantities: list[int],
        risk_manager: RiskManager | None = None,
        initial_capital: float = 100000.0,
        lot_size: int = 1,
        circuit_breaker_active: bool = False
    ) -> BacktestResult:
        """Run backtest with pre-computed target quantities.
        
        Simpler interface for testing. Assumes:
        - target_quantities[i] is the target position after seeing bars[0:i+1]
        - Signal generated at bar[i] close (risk evaluated then)
        - Fill executed at bar[i+1] open
        - A signal on the LAST bar has no next open to trade at, so it is not
          executed; any open position is marked to market at the final close
        
        Args:
            bars: Historical OHLCV bars
            target_quantities: Target position at each bar (aligned with bars)
            risk_manager: Optional risk manager to apply constraints
            initial_capital: Starting capital
            lot_size: Contract multiplier; quantities are in lots, P&L and costs
                      are scaled by lot_size (e.g. 75 for NIFTY futures)
            circuit_breaker_active: Macro circuit breaker state passed to risk checks
            
        Returns:
            BacktestResult with trade history and P&L. equity_curve has one
            point for the initial capital plus one per bar, marked at that
            bar's close using only fills that had happened by then.
        """
        if len(bars) == 0:
            raise ValueError("bars cannot be empty")
        
        if len(target_quantities) != len(bars):
            raise ValueError("target_quantities must have same length as bars")
        
        if lot_size < 1:
            raise ValueError("lot_size must be at least 1")
        
        instrument = bars[0].instrument
        position = Position(instrument=instrument, multiplier=lot_size)
        fills: list[Fill] = []
        equity_curve: list[float] = [initial_capital]
        total_costs = 0.0
        total_slippage = 0.0
        pending_qty = 0          # order decided at previous bar's close
        pending_signal_bar = -1
        
        for i, current_bar in enumerate(bars):
            # 1. Execute the order decided at bar[i-1] close at bar[i] open
            if pending_qty != 0:
                side = Side.BUY if pending_qty > 0 else Side.SELL
                abs_qty = abs(pending_qty)
                slippage = self.slippage_model.calculate_slippage(side, current_bar.open, abs_qty)
                fill_price = current_bar.open + slippage if side == Side.BUY else current_bar.open - slippage
                
                fill = Fill(
                    order_id=f"backtest_{pending_signal_bar}",
                    instrument=instrument,
                    side=side,
                    quantity=abs_qty,
                    price=fill_price,
                    filled_at=current_bar.timestamp
                )
                fills.append(fill)
                total_costs += self.cost_model.calculate_costs(fill, multiplier=lot_size)
                total_slippage += slippage * abs_qty * lot_size
                position.apply_fill(fill)
                pending_qty = 0
            
            # 2. Mark to market at this bar's close
            equity = initial_capital + position.realized_pnl + position.unrealized_pnl(current_bar.close) - total_costs
            equity_curve.append(equity)
            
            # 3. Decide the order for the next bar (none possible after the last bar)
            if i == len(bars) - 1:
                break
            
            target_qty = target_quantities[i]
            if risk_manager:
                decision = risk_manager.evaluate(
                    instrument=instrument,
                    desired_quantity=target_qty,
                    current_position=position,
                    circuit_breaker_active=circuit_breaker_active
                )
                if not decision.allowed:
                    continue  # Risk rejected - hold current position
                target_qty = decision.target_quantity
            
            pending_qty = target_qty - position.quantity
            pending_signal_bar = i
        
        final_bar = bars[-1]
        gross_pnl = position.realized_pnl + position.unrealized_pnl(final_bar.close)
        net_pnl = gross_pnl - total_costs
        returns_pct = (net_pnl / initial_capital) * 100 if initial_capital > 0 else 0.0
        
        return BacktestResult(
            instrument=instrument,
            fills=fills,
            final_position=position,
            gross_pnl=gross_pnl,
            transaction_costs=total_costs,
            slippage_costs=total_slippage,
            net_pnl=net_pnl,
            returns_pct=returns_pct,
            equity_curve=equity_curve,
            total_trades=len(fills)
        )
