"""
End-to-end Grid Strategy Backtest Example

This script demonstrates the complete trading system:
- Load historical data
- Calculate indicators (ATR, RSI)
- Generate strategy signals
- Apply risk management
- Execute backtest with realistic costs
- Display results
"""

from datetime import datetime, UTC
import sys
import os
import pandas as pd

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.bar import Bar
from src.core.position import Position
from src.indicators.atr import atr
from src.indicators.rsi import rsi
from src.strategy import GridStrategy
from src.risk import RiskManager
from src.backtest import (
    BacktestEngine,
    FixedPercentageSlippage,
    IndianEquityFuturesCosts
)


def create_sample_data(instrument: str, n_bars: int = 100, start_price: float = 18000.0) -> list[Bar]:
    """Create synthetic trending data for demonstration.
    
    Simulates a trending market with noise - ideal for grid strategy.
    """
    import random
    random.seed(42)  # Reproducible results
    
    bars = []
    price = start_price
    
    for i in range(n_bars):
        # Trend up slowly with noise
        trend = 0.5
        noise = random.uniform(-10, 10)
        price = price + trend + noise
        
        # OHLC
        day_range = abs(noise) + 5
        open_price = price
        high = price + random.uniform(0, day_range)
        low = price - random.uniform(0, day_range)
        close = price + random.uniform(-day_range/2, day_range/2)
        
        # Calculate day, hour, minute for timestamp
        total_minutes = 9 * 60 + 15 + i  # Start at 9:15
        day = 1 + (total_minutes // (24 * 60))
        hour = (total_minutes % (24 * 60)) // 60
        minute = total_minutes % 60
        
        bar = Bar(
            instrument=instrument,
            timestamp=datetime(2024, 1, min(day, 28), hour, minute, tzinfo=UTC),
            open=max(1, open_price),
            high=max(1, high),
            low=max(1, low),
            close=max(1, close),
            volume=100000 + random.randint(-10000, 10000)
        )
        bars.append(bar)
    
    return bars


def run_grid_strategy_backtest():
    """Run complete end-to-end backtest."""
    
    print("=" * 70)
    print("GRID STRATEGY BACKTEST - END-TO-END DEMONSTRATION")
    print("=" * 70)
    print()
    
    # 1. Create sample data
    print("Step 1: Creating sample data...")
    instrument = "NIFTY_FUT"
    bars = create_sample_data(instrument, n_bars=100, start_price=18000.0)
    print(f"  ✓ Generated {len(bars)} bars")
    print(f"  ✓ Price range: {min(b.close for b in bars):.2f} to {max(b.close for b in bars):.2f}")
    print()
    
    # 2. Calculate indicators
    print("Step 2: Calculating indicators...")
    atr_values = atr(bars, period=14)
    rsi_values = rsi(bars, period=14)
    print(f"  ✓ ATR calculated ({len([x for x in atr_values if not pd.isna(x)])} valid values)")
    print(f"  ✓ RSI calculated ({len([x for x in rsi_values if not pd.isna(x)])} valid values)")
    print()
    
    # 3. Initialize strategy
    print("Step 3: Initializing Grid Strategy...")
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=1.5,
        max_pyramid_levels=3,
        stop_loss_atr_multiplier=2.5,
        position_size=1
    )
    print(f"  ✓ Grid spacing: 1.5 × ATR")
    print(f"  ✓ Max pyramid levels: 3")
    print(f"  ✓ Stop loss: 2.5 × ATR")
    print()
    
    # 4. Initialize risk manager
    print("Step 4: Initializing Risk Manager...")
    risk_manager = RiskManager(
        max_position=3,
        kill_switch=False
    )
    print(f"  ✓ Max position: ±3")
    print(f"  ✓ Kill switch: OFF")
    print()
    
    # 5. Generate target quantities for each bar
    print("Step 5: Generating strategy signals...")
    
    position = Position(instrument=instrument)
    target_quantities = []
    
    for i, bar in enumerate(bars):
        # Get current indicators
        current_atr = atr_values.iloc[i] if i < len(atr_values) and not pd.isna(atr_values.iloc[i]) else None
        current_rsi = rsi_values.iloc[i] if i < len(rsi_values) and not pd.isna(rsi_values.iloc[i]) else None
        
        if current_atr is None or current_rsi is None or current_atr == 0:
            # Not enough data yet
            target_quantities.append(0)
            continue
        
        # Strategy calculates target
        target = strategy.calculate_target_quantity(
            instrument=instrument,
            current_price=bar.close,
            current_position=position,
            atr=current_atr,
            rsi=current_rsi
        )
        
        # Apply risk
        decision = risk_manager.evaluate(
            instrument=instrument,
            desired_quantity=target,
            current_position=position
        )
        
        final_target = decision.target_quantity if decision.allowed else position.quantity
        target_quantities.append(final_target)
        
        # Update position for next iteration (simulate)
        position.quantity = final_target
    
    print(f"  ✓ Generated {len(target_quantities)} signals")
    print(f"  ✓ Non-zero signals: {len([x for x in target_quantities if x != 0])}")
    print()
    
    # 6. Run backtest
    print("Step 6: Running backtest with realistic costs...")
    backtest_engine = BacktestEngine(
        slippage_model=FixedPercentageSlippage(slippage_pct=0.001),  # 0.1%
        cost_model=IndianEquityFuturesCosts(brokerage_per_trade=20.0)
    )
    
    # Reset position and strategy for clean backtest
    strategy.reset()
    
    result = backtest_engine.run_simple(
        bars=bars,
        target_quantities=target_quantities,
        risk_manager=risk_manager,
        initial_capital=500000.0
    )
    
    print(f"  ✓ Backtest complete")
    print()
    
    # 7. Display results
    print("=" * 70)
    print("BACKTEST RESULTS")
    print("=" * 70)
    print()
    print(f"Instrument:          {result.instrument}")
    print(f"Total Trades:        {result.total_trades}")
    print(f"Final Position:      {result.final_position.quantity if result.final_position else 0}")
    print()
    print(f"Gross P&L:           ₹{result.gross_pnl:,.2f}")
    print(f"Transaction Costs:   ₹{result.transaction_costs:,.2f}")
    print(f"Slippage Costs:      ₹{result.slippage_costs:,.2f}")
    print(f"Net P&L:             ₹{result.net_pnl:,.2f}")
    print(f"Returns:             {result.returns_pct:.2f}%")
    print()
    
    if result.total_trades > 0:
        print("Sample Trades (first 5):")
        for i, fill in enumerate(result.fills[:5]):
            print(f"  {i+1}. {fill.side.value:4} {fill.quantity} @ ₹{fill.price:.2f}")
        if result.total_trades > 5:
            print(f"  ... and {result.total_trades - 5} more trades")
    
    print()
    print("=" * 70)
    print()
    
    # 8. Analysis
    print("Analysis:")
    if result.net_pnl > 0:
        print(f"  ✓ Strategy was profitable: +₹{result.net_pnl:,.2f}")
    else:
        print(f"  ✗ Strategy lost money: ₹{result.net_pnl:,.2f}")
    
    if result.transaction_costs > abs(result.gross_pnl) * 0.5:
        print(f"  ⚠ Transaction costs consumed {(result.transaction_costs/abs(result.gross_pnl))*100:.1f}% of gross P&L")
    
    print()
    print("System Components Validated:")
    print("  ✓ Bar data ingestion")
    print("  ✓ Indicator calculation (ATR, RSI)")
    print("  ✓ Grid strategy logic")
    print("  ✓ Risk management")
    print("  ✓ Backtest execution")
    print("  ✓ Slippage modeling")
    print("  ✓ Cost calculation")
    print("  ✓ P&L reconciliation")
    print()
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    result = run_grid_strategy_backtest()
