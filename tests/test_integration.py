"""End-to-end integration tests."""

from datetime import datetime, UTC
from src.core.bar import Bar
from src.core.position import Position
from src.indicators.atr import atr
from src.indicators.rsi import rsi
from src.strategy import GridStrategy, StopAndReverseStrategy
from src.risk import RiskManager
from src.backtest import BacktestEngine, FixedPercentageSlippage, ZeroCosts


def create_trending_bars(instrument: str, n: int, start_price: float = 100.0, trend: float = 1.0) -> list[Bar]:
    """Create bars with upward trend."""
    bars = []
    price = start_price
    for i in range(n):
        price += trend
        # Calculate proper timestamp (handle minute overflow)
        total_minutes = 9 * 60 + 15 + i  # Start at 9:15
        hour = (total_minutes // 60) % 24
        minute = total_minutes % 60
        bar = Bar(
            instrument=instrument,
            timestamp=datetime(2024, 1, 1, hour, minute, tzinfo=UTC),
            open=price,
            high=price + 2,
            low=price - 2,
            close=price,
            volume=1000
        )
        bars.append(bar)
    return bars


def test_integration_grid_strategy_with_indicators():
    """Integration: Bars → Indicators → Grid Strategy → Risk → Backtest."""
    # Create data
    bars = create_trending_bars("NIFTY", n=50, start_price=100.0, trend=0.5)
    
    # Calculate indicators
    atr_values = atr(bars, period=14)
    rsi_values = rsi(bars, period=14)
    
    # Initialize components
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=2.0,
        max_pyramid_levels=2,
        position_size=1
    )
    risk = RiskManager(max_position=3)
    engine = BacktestEngine(cost_model=ZeroCosts())
    
    # Generate signals
    position = Position(instrument="NIFTY")
    targets = []
    
    import pandas as pd
    for i, bar in enumerate(bars):
        atr_val = atr_values.iloc[i] if not pd.isna(atr_values.iloc[i]) else None
        rsi_val = rsi_values.iloc[i] if not pd.isna(rsi_values.iloc[i]) else None
        
        if atr_val is None or rsi_val is None or atr_val == 0:
            targets.append(0)
            continue
        
        target = strategy.calculate_target_quantity(
            instrument="NIFTY",
            current_price=bar.close,
            current_position=position,
            atr=atr_val,
            rsi=rsi_val
        )
        
        decision = risk.evaluate("NIFTY", target, position)
        final_target = decision.target_quantity if decision.allowed else position.quantity
        targets.append(final_target)
        position.quantity = final_target
    
    # Run backtest
    strategy.reset()
    result = engine.run_simple(bars, targets, risk_manager=risk)
    
    # Verify system worked
    assert result is not None
    assert result.instrument == "NIFTY"
    assert len(result.equity_curve) > 0


def test_integration_sar_strategy_simple():
    """Integration: SAR Strategy → Backtest."""
    bars = create_trending_bars("NIFTY", n=30, start_price=100.0, trend=1.0)
    
    # Calculate RSI
    rsi_values = rsi(bars, period=14)
    
    # SAR strategy
    strategy = StopAndReverseStrategy(position_size=1)
    position = Position(instrument="NIFTY")
    targets = []
    
    import pandas as pd
    for i, bar in enumerate(bars):
        rsi_val = rsi_values.iloc[i] if not pd.isna(rsi_values.iloc[i]) else None
        
        if rsi_val is None:
            targets.append(0)
            continue
        
        target = strategy.calculate_target_quantity(
            instrument="NIFTY",
            current_position=position,
            rsi=rsi_val
        )
        targets.append(target)
        position.quantity = target
    
    # Backtest
    engine = BacktestEngine()
    result = engine.run_simple(bars, targets)
    
    assert result is not None
    assert result.total_trades >= 0


def test_integration_risk_limits_strategy():
    """Integration: Strategy wants 5, Risk caps at 2."""
    bars = create_trending_bars("NIFTY", n=20, start_price=100.0)
    
    # Strategy that wants position of 5
    targets = [5] * 20
    
    # Risk caps at 2
    risk = RiskManager(max_position=2)
    
    # Backtest
    engine = BacktestEngine()
    result = engine.run_simple(bars, targets, risk_manager=risk)
    
    # Position should be capped
    assert result.final_position.quantity <= 2
    
    # First fill should be for 2, not 5
    if len(result.fills) > 0:
        assert result.fills[0].quantity == 2


def test_integration_slippage_increases_costs():
    """Integration: Slippage should reduce net P&L."""
    bars = create_trending_bars("NIFTY", n=10, start_price=100.0, trend=2.0)
    
    # Simple buy and hold
    targets = [1] * 9 + [0]
    
    # Run without slippage
    engine_no_slip = BacktestEngine()
    result_no_slip = engine_no_slip.run_simple(bars, targets)
    
    # Run with slippage
    engine_with_slip = BacktestEngine(
        slippage_model=FixedPercentageSlippage(slippage_pct=0.01)
    )
    result_with_slip = engine_with_slip.run_simple(bars, targets)
    
    # Net P&L should be lower with slippage
    assert result_with_slip.net_pnl < result_no_slip.net_pnl
    assert result_with_slip.slippage_costs > 0


def test_integration_full_system_produces_reasonable_results():
    """Integration: Full system should produce coherent results."""
    bars = create_trending_bars("NIFTY", n=50, start_price=100.0, trend=0.5)
    
    # Setup full system
    atr_values = atr(bars, period=14)
    rsi_values = rsi(bars, period=14)
    
    strategy = GridStrategy(position_size=1)
    risk = RiskManager(max_position=5)
    engine = BacktestEngine()
    
    # Generate signals
    position = Position(instrument="NIFTY")
    targets = []
    
    import pandas as pd
    for i, bar in enumerate(bars):
        atr_val = atr_values.iloc[i] if not pd.isna(atr_values.iloc[i]) else None
        rsi_val = rsi_values.iloc[i] if not pd.isna(rsi_values.iloc[i]) else None
        
        if atr_val and rsi_val and atr_val > 0:
            target = strategy.calculate_target_quantity(
                "NIFTY", bar.close, position, atr_val, rsi_val
            )
            decision = risk.evaluate("NIFTY", target, position)
            final = decision.target_quantity if decision.allowed else position.quantity
            targets.append(final)
            position.quantity = final
        else:
            targets.append(0)
    
    # Backtest
    strategy.reset()
    result = engine.run_simple(bars, targets, risk_manager=risk)
    
    # Sanity checks
    assert result.instrument == "NIFTY"
    assert result.total_trades >= 0
    assert len(result.equity_curve) > 0
    assert result.equity_curve[0] == 100000.0  # initial capital
    
    # If trades happened, verify P&L makes sense
    if result.total_trades > 0:
        # Gross P&L should be realized + unrealized
        if result.final_position:
            expected_gross = result.final_position.realized_pnl + result.final_position.unrealized_pnl(bars[-1].close)
            assert abs(result.gross_pnl - expected_gross) < 0.01
        
        # Net P&L = Gross - Costs
        expected_net = result.gross_pnl - result.transaction_costs
        assert abs(result.net_pnl - expected_net) < 0.01


def test_integration_components_are_isolated():
    """Integration: Same data, different strategies → different results."""
    bars = create_trending_bars("NIFTY", n=30, start_price=100.0)
    
    # Strategy 1: Always long
    targets_long = [1] * 30
    
    # Strategy 2: Always short
    targets_short = [-1] * 30
    
    engine = BacktestEngine()
    
    result_long = engine.run_simple(bars, targets_long)
    result_short = engine.run_simple(bars, targets_short)
    
    # Should have opposite P&L (approximately)
    # Long should profit in uptrend, short should lose
    assert result_long.gross_pnl > result_short.gross_pnl
