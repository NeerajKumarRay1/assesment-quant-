"""Tests for backtest engine."""

import pytest
from datetime import datetime, UTC
from src.backtest import (
    BacktestEngine,
    FixedPercentageSlippage,
    ZeroSlippage,
    IndianEquityFuturesCosts,
    ZeroCosts,
    FixedCostPerTrade
)
from src.core.bar import Bar
from src.core.order import Side
from src.risk import RiskManager


def create_bars(instrument: str, n: int, start_price: float = 100.0) -> list[Bar]:
    """Helper to create test bars."""
    bars = []
    for i in range(n):
        bar = Bar(
            instrument=instrument,
            timestamp=datetime(2024, 1, 1, 9, 15 + i, tzinfo=UTC),
            open=start_price + i,
            high=start_price + i + 1,
            low=start_price + i - 1,
            close=start_price + i,
            volume=1000
        )
        bars.append(bar)
    return bars


def test_backtest_no_trades_when_flat():
    """Stay flat throughout → no fills, zero P&L."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 10)
    targets = [0] * 10  # Stay flat
    
    result = engine.run_simple(bars, targets)
    
    assert len(result.fills) == 0
    assert result.total_trades == 0
    assert result.net_pnl == 0.0


def test_backtest_single_buy_and_hold():
    """Buy 1 at start, hold, sell at end."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 10, start_price=100.0)
    
    # Buy signal at bar 0, flat signal at bar 8 (filled at bar 9 open)
    targets = [1, 1, 1, 1, 1, 1, 1, 1, 0, 0]
    
    result = engine.run_simple(bars, targets)
    
    # Should have 2 trades: buy and sell
    assert result.total_trades == 2
    
    # First fill: buy at bar[1].open = 101
    buy_fill = result.fills[0]
    assert buy_fill.side == Side.BUY
    assert buy_fill.quantity == 1
    assert buy_fill.price == 101.0
    
    # Second fill: sell at bar[9].open = 109
    sell_fill = result.fills[1]
    assert sell_fill.side == Side.SELL
    assert sell_fill.quantity == 1
    assert sell_fill.price == 109.0
    
    # P&L = 109 - 101 = 8 (no costs)
    assert result.gross_pnl == 8.0
    assert result.net_pnl == 8.0


def test_backtest_fill_happens_at_next_bar_open():
    """Verify bar-accurate execution: signal at bar[i] → fill at bar[i+1].open."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    
    # Signal to buy at bar 0
    targets = [1, 1, 1, 1, 1]
    
    result = engine.run_simple(bars, targets)
    
    # Fill should be at bar[1].open, not bar[0].close
    fill = result.fills[0]
    assert fill.price == bars[1].open  # 101.0


def test_backtest_with_fixed_percentage_slippage():
    """Slippage should increase costs."""
    slippage = FixedPercentageSlippage(slippage_pct=0.01)  # 1%
    engine = BacktestEngine(slippage_model=slippage)
    
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 0, 0]  # Buy, hold, sell (exit filled at bar 4 open)

    result = engine.run_simple(bars, targets)

    # Buy at 101 + 1% = 102.01
    buy_fill = result.fills[0]
    assert buy_fill.price == pytest.approx(102.01)
    
    # Sell at 104 - 1% = 102.96
    sell_fill = result.fills[1]
    assert sell_fill.price == pytest.approx(102.96)
    
    # Gross P&L = 102.96 - 102.01 = 0.95 (reduced by slippage)
    assert result.gross_pnl == pytest.approx(0.95, abs=0.01)
    assert result.slippage_costs > 0


def test_backtest_with_transaction_costs():
    """Transaction costs should reduce net P&L."""
    costs = FixedCostPerTrade(cost_per_trade=10.0)
    engine = BacktestEngine(cost_model=costs)

    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 0, 0]
    
    result = engine.run_simple(bars, targets)
    
    # Gross P&L = 104 - 101 = 3
    # Costs = 2 trades × 10 = 20
    # Net P&L = 3 - 20 = -17
    assert result.gross_pnl == 3.0
    assert result.transaction_costs == 20.0
    assert result.net_pnl == -17.0


def test_backtest_with_risk_manager():
    """Risk manager should limit position size."""
    risk = RiskManager(max_position=2)
    engine = BacktestEngine()
    
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [5, 5, 5, 0, 0]  # Try to buy 5, but risk caps at 2
    
    result = engine.run_simple(bars, targets, risk_manager=risk)
    
    # Should only buy 2 (capped by risk)
    buy_fill = result.fills[0]
    assert buy_fill.quantity == 2
    
    # Final sell should also be 2
    sell_fill = result.fills[1]
    assert sell_fill.quantity == 2


def test_backtest_kill_switch_blocks_new_positions():
    """Kill switch should prevent new exposure."""
    risk = RiskManager(max_position=10, kill_switch=True)
    engine = BacktestEngine()
    
    bars = create_bars("NIFTY", 5)
    targets = [1, 1, 1, 1, 1]  # Try to buy
    
    result = engine.run_simple(bars, targets, risk_manager=risk)
    
    # No fills due to kill switch
    assert len(result.fills) == 0


def test_backtest_equity_curve_tracks_value():
    """Equity curve should track portfolio value over time."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 1, 0]
    initial_capital = 10000.0
    
    result = engine.run_simple(bars, targets, initial_capital=initial_capital)
    
    # Should have equity: initial + after each bar + final
    assert len(result.equity_curve) > len(bars)
    
    # First equity = initial capital
    assert result.equity_curve[0] == initial_capital
    
    # Last equity = initial + net P&L
    assert result.equity_curve[-1] == initial_capital + result.net_pnl


def test_backtest_multiple_round_trips():
    """Multiple buy-sell cycles."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 11, start_price=100.0)

    # Buy, sell, buy, sell (final bar's signal can't be executed)
    targets = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0]
    
    result = engine.run_simple(bars, targets)
    
    # Should have 10 fills (5 buys + 5 sells)
    assert result.total_trades == 10


def test_backtest_short_position():
    """Going short should work."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    
    # Short 1, cover on bar 3 signal (filled at bar 4 open)
    targets = [-1, -1, -1, 0, 0]
    
    result = engine.run_simple(bars, targets)
    
    # First fill: sell short
    short_fill = result.fills[0]
    assert short_fill.side == Side.SELL
    assert short_fill.quantity == 1
    
    # Cover at higher price → loss
    cover_fill = result.fills[1]
    assert cover_fill.side == Side.BUY
    
    # Shorted at 101, covered at 104 → loss of 3
    assert result.gross_pnl == -3.0


def test_backtest_no_lookahead_signal_uses_past_data_only():
    """Test that signals only use data up to current bar (no future peeking)."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    
    # This is implicit in our design: targets[i] computed from bars[0:i+1]
    # Fill happens at bars[i+1].open
    
    # If we had lookahead, we'd know bars[1].open before deciding at bars[0]
    # Our design prevents this by filling one bar later
    
    targets = [1, 1, 1, 1, 0]
    result = engine.run_simple(bars, targets)
    
    # Buy fill should be at bars[1].open (101), not bars[0] anything
    assert result.fills[0].price == 101.0
    # This proves no lookahead - we can't know bars[1].open when at bars[0]


def test_backtest_empty_bars_raises():
    """Empty bars should raise error."""
    engine = BacktestEngine()
    
    with pytest.raises(ValueError, match="bars cannot be empty"):
        engine.run_simple([], [])


def test_backtest_mismatched_lengths_raises():
    """Targets and bars must have same length."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5)
    targets = [1, 1, 1]  # Wrong length
    
    with pytest.raises(ValueError, match="same length"):
        engine.run_simple(bars, targets, targets)


def test_slippage_model_zero_slippage():
    """ZeroSlippage should return 0."""
    model = ZeroSlippage()
    slippage = model.calculate_slippage(Side.BUY, 100.0, 1)
    assert slippage == 0.0


def test_slippage_model_fixed_percentage():
    """FixedPercentageSlippage should return percentage of price."""
    model = FixedPercentageSlippage(slippage_pct=0.01)  # 1%
    
    slippage = model.calculate_slippage(Side.BUY, 100.0, 1)
    assert slippage == 1.0  # 1% of 100
    
    slippage = model.calculate_slippage(Side.SELL, 200.0, 5)
    assert slippage == 2.0  # 1% of 200


def test_slippage_model_rejects_negative():
    """Negative slippage should raise error."""
    with pytest.raises(ValueError):
        FixedPercentageSlippage(slippage_pct=-0.01)


def test_cost_model_zero_costs():
    """ZeroCosts should return 0."""
    from src.core.order import Fill
    model = ZeroCosts()
    fill = Fill(order_id="x", instrument="NIFTY", side=Side.BUY, quantity=1, price=100.0)
    
    assert model.calculate_costs(fill) == 0.0


def test_cost_model_fixed_cost():
    """FixedCostPerTrade should return fixed amount."""
    from src.core.order import Fill
    model = FixedCostPerTrade(cost_per_trade=25.0)
    fill = Fill(order_id="x", instrument="NIFTY", side=Side.BUY, quantity=1, price=100.0)
    
    assert model.calculate_costs(fill) == 25.0


def test_cost_model_indian_futures():
    """IndianEquityFuturesCosts should calculate realistic costs."""
    from src.core.order import Fill
    model = IndianEquityFuturesCosts(
        brokerage_per_trade=20.0,
        stt_rate=0.000125,
        exchange_charge_rate=0.00002
    )
    
    # Buy fill
    buy_fill = Fill(order_id="x", instrument="NIFTY", side=Side.BUY, quantity=50, price=18000.0)
    buy_costs = model.calculate_costs(buy_fill)
    
    # Should include: brokerage + exchange + SEBI + GST + stamp duty (no STT on buy)
    assert buy_costs > 20.0  # At least brokerage
    assert buy_costs < 100.0  # Reasonable total on ₹9L notional
    
    # Sell fill (includes STT)
    sell_fill = Fill(order_id="y", instrument="NIFTY", side=Side.SELL, quantity=50, price=18000.0)
    sell_costs = model.calculate_costs(sell_fill)
    
    # Sell should cost more (has STT)
    assert sell_costs > buy_costs


def test_backtest_returns_percentage():
    """Returns should be calculated as percentage of initial capital."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 1, 0]
    initial_capital = 10000.0
    
    result = engine.run_simple(bars, targets, initial_capital=initial_capital)
    
    # Net P&L = 3 (from 101 to 104)
    # Returns = (3 / 10000) * 100 = 0.03%
    expected_returns = (result.net_pnl / initial_capital) * 100
    assert result.returns_pct == pytest.approx(expected_returns)


def test_backtest_final_position_correct():
    """Final position should match last target."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 2, 3, 1, 1]  # Bar 3 signal (1) fills at bar 4; bar 4 signal can't fill

    result = engine.run_simple(bars, targets)

    # Final position = 1
    assert result.final_position.quantity == 1


def test_backtest_last_bar_signal_is_not_executed():
    """No bar after the last one → its signal has no open to trade at."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 1, 0]

    result = engine.run_simple(bars, targets)

    assert result.total_trades == 1
    assert result.final_position.quantity == 1
    # Open position is marked to market at final close: 104 - 101
    assert result.gross_pnl == 3.0


def test_backtest_equity_curve_one_point_per_bar():
    """Equity curve = initial capital + one mark per bar, using only past fills."""
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 1, 1]

    result = engine.run_simple(bars, targets, initial_capital=1000.0)

    assert len(result.equity_curve) == len(bars) + 1
    # Bar 0: signal only, no fill yet → still flat
    assert result.equity_curve[1] == 1000.0
    # Bar 1: bought at 101 open, close 101 → 0; bar 4: close 104 → +3
    assert result.equity_curve[2] == 1000.0
    assert result.equity_curve[-1] == 1003.0


def test_backtest_equity_curve_has_point_when_risk_rejects():
    """Rejected signals must not create gaps in the equity curve."""
    risk = RiskManager(max_position=10, kill_switch=True)
    engine = BacktestEngine()
    bars = create_bars("NIFTY", 5)

    result = engine.run_simple(bars, [1] * 5, risk_manager=risk)

    assert len(result.equity_curve) == len(bars) + 1


def test_backtest_lot_size_scales_pnl_and_costs():
    """Quantities are lots; P&L and notional-based costs scale by lot size."""
    bars = create_bars("NIFTY", 5, start_price=100.0)
    targets = [1, 1, 1, 0, 0]

    one = BacktestEngine(cost_model=IndianEquityFuturesCosts()).run_simple(bars, targets)
    lots = BacktestEngine(cost_model=IndianEquityFuturesCosts()).run_simple(bars, targets, lot_size=75)

    assert one.gross_pnl == 3.0
    assert lots.gross_pnl == 3.0 * 75
    # Flat brokerage doesn't scale, percentage charges do
    assert one.transaction_costs < lots.transaction_costs < one.transaction_costs * 75
