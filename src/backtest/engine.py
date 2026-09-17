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
        initial_capital: float = 100000.0
    ) -> BacktestResult:
        """Run backtest with pre-computed target quantities.
        
        Simpler interface for testing. Assumes:
        - target_quantities[i] is the target position after seeing bars[0:i+1]
        - Signal generated at bar[i] close
        - Fill executed at bar[i+1] open
        
        Args:
            bars: Historical OHLCV bars
            target_quantities: Target position at each bar (aligned with bars)
            risk_manager: Optional risk manager to apply constraints
            initial_capital: Starting capital
            
        Returns:
            BacktestResult with trade history and P&L
        """
        if len(bars) == 0:
            raise ValueError("bars cannot be empty")
        
        if len(target_quantities) != len(bars):
            raise ValueError("target_quantities must have same length as bars")
        
        instrument = bars[0].instrument
        position = Position(instrument=instrument)
        fills: list[Fill] = []
        equity_curve: list[float] = [initial_capital]
        total_costs = 0.0
        total_slippage = 0.0
        
        # Process each bar
        for i in range(len(bars)):
            current_bar = bars[i]
            
            # Target quantity determined at current bar close
            raw_target = target_quantities[i]
            
            # Apply risk manager if provided
            if risk_manager:
                decision = risk_manager.evaluate(
                    instrument=instrument,
                    desired_quantity=raw_target,
                    current_position=position
                )
                if not decision.allowed:
                    continue  # Risk rejected
                target_qty = decision.target_quantity
            else:
                target_qty = raw_target
            
            # Calculate quantity to trade
            qty_to_trade = target_qty - position.quantity
            
            if qty_to_trade == 0:
                # No trade needed
                equity = initial_capital + position.realized_pnl + position.unrealized_pnl(current_bar.close)
                equity_curve.append(equity)
                continue
            
            # Determine side
            side = Side.BUY if qty_to_trade > 0 else Side.SELL
            abs_qty = abs(qty_to_trade)
            
            # Fill at next bar open + slippage
            # If this is the last bar, use current bar close as approximation
            if i < len(bars) - 1:
                fill_price_base = bars[i + 1].open
            else:
                fill_price_base = current_bar.close
            
            slippage = self.slippage_model.calculate_slippage(side, fill_price_base, abs_qty)
            
            # Apply slippage direction
            if side == Side.BUY:
                fill_price = fill_price_base + slippage  # Pay more
            else:
                fill_price = fill_price_base - slippage  # Receive less
            
            # Create fill
            fill = Fill(
                order_id=f"backtest_{i}",
                instrument=instrument,
                side=side,
                quantity=abs_qty,
                price=fill_price
            )
            fills.append(fill)
            
            # Calculate costs
            costs = self.cost_model.calculate_costs(fill)
            total_costs += costs
            total_slippage += slippage * abs_qty
            
            # Apply fill to position
            position.apply_fill(fill)
            
            # Update equity
            equity = initial_capital + position.realized_pnl + position.unrealized_pnl(current_bar.close) - total_costs
            equity_curve.append(equity)
        
        # Final equity at last bar
        final_bar = bars[-1]
        final_equity = initial_capital + position.realized_pnl + position.unrealized_pnl(final_bar.close) - total_costs
        equity_curve.append(final_equity)
        
        # Calculate net P&L
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
