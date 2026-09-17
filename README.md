# Quantitative Trading System

A production-grade algorithmic trading system implementing Grid and Stop-and-Reverse strategies with comprehensive risk management and realistic backtesting.

## Quick Start

```bash
# Install dependencies
pip install -e .

# Run tests
python -m pytest

# Run demonstration
python examples/grid_backtest_example.py
```

## Architecture

The system follows a layered architecture with clear separation of concerns:

```
Market Data -> Indicators -> Strategy -> Risk Manager -> Order Manager -> Broker
                                                                           |
                                                                         Fills
                                                                           |
                                                                        Position
                                                                           |
                                                                          P&L
```

## Components

### Core Domain
Foundation objects representing trading concepts:
- Order, Fill: Immutable trading events
- Position: Tracks holdings, average price, realized/unrealized P&L
- Instrument: Contract specifications (lot size, tick size, expiry)
- Bar: OHLCV candlestick data

### Broker Layer
Abstraction for order execution with failure mode handling:
- Broker interface: Abstract base for any broker implementation
- MockBroker: Simulated execution with idempotency and failure modes (timeout, reject, disconnect)

### Market Data
Abstraction for historical and live data:
- MarketData interface: Abstract base for data providers
- MockMarketData: Simulated historical bars and tick streams

### Technical Indicators
Four categories with shared mathematical utilities:
- Trend: EMA (Exponential Moving Average)
- Momentum: RSI (Relative Strength Index)
- Volatility: ATR (Average True Range)
- Volume: OBV (On-Balance Volume)

### Trading Strategies

**Grid Strategy**
- ATR-based dynamic spacing adapts to volatility
- Pyramiding up to 3 levels on favorable moves
- ATR-based stop loss
- RSI for entry signals

**Stop-and-Reverse Strategy**
- Always-in position (long or short)
- State machine: FLAT, LONG, SHORT
- RSI-based reversal signals

### Risk Management
Position and exposure controls:
- Position caps (configurable max long/short)
- Kill switch (blocks new exposure, allows reduction)
- Risk decisions with rejection reasons

### Order Manager
Production-ready order lifecycle management:
- Idempotent submission using client_order_id
- Automatic retry on timeout
- State reconciliation after restarts
- Crash recovery support

### Backtesting Engine
Realistic historical simulation:
- Bar-accurate fills (signal at close, fill at next open)
- Slippage modeling
- Transaction costs (Indian futures: brokerage, STT, exchange fees, GST)
- No lookahead bias
- P&L reconciliation

## Key Design Decisions

### Idempotency
Orders use client_order_id as an idempotency key. Retrying the same order ID returns the original fill instead of creating duplicates. This makes network retries safe.

### Bar-Accurate Execution
Signals generated at bar[t] close are executed at bar[t+1] open. This prevents lookahead bias and matches realistic trading constraints.

### Separation of Concerns
- Strategy: Decides what to trade based on market signals
- Risk: Decides how much is allowed based on limits
- OrderManager: Handles execution mechanics
- Broker: Performs actual execution

### Immutability
Orders and Fills are immutable dataclasses representing facts. Position is the only mutable object because it represents derived state that updates with new fills.

## Testing

The system has 140 tests covering:
- Unit tests for individual components
- Integration tests for component interaction
- Edge cases and failure modes
- Regression tests for strategy logic

Run tests:
```bash
python -m pytest                    # All tests
python -m pytest -v                 # Verbose output
python -m pytest tests/test_grid_strategy.py  # Specific component
```

## Example Usage

```python
from src.backtest import BacktestEngine, FixedPercentageSlippage
from src.strategy import GridStrategy
from src.risk import RiskManager

# Initialize components
strategy = GridStrategy(
    grid_spacing_atr_multiplier=1.5,
    max_pyramid_levels=3
)
risk = RiskManager(max_position=5)
engine = BacktestEngine(
    slippage_model=FixedPercentageSlippage(0.001)
)

# Run backtest
result = engine.run_simple(bars, targets, risk_manager=risk)

# Access results
print(f"Net P&L: {result.net_pnl:,.2f}")
print(f"Total Trades: {result.total_trades}")
print(f"Returns: {result.returns_pct:.2f}%")
```

## Project Structure

```
src/
├── core/           # Domain objects (Order, Position, Fill, etc.)
├── broker/         # Broker abstraction and MockBroker
├── market_data/    # Market data abstraction and MockMarketData
├── indicators/     # Technical indicators (ATR, RSI, EMA, OBV)
├── strategy/       # Trading strategies (Grid, Stop-and-Reverse)
├── risk/           # Risk management
├── execution/      # Order manager
└── backtest/       # Backtesting engine

tests/              # 140 tests
examples/           # End-to-end demonstrations
```

## Dependencies

```
Python >= 3.11
pandas >= 2.2
numpy >= 1.26
pytest >= 8.0 (dev)
```

All dependencies are standard libraries commonly used in quantitative finance.

## Technical Details

### Indian Futures Cost Model
Transaction costs include:
- Brokerage: Fixed per trade (typically Rs. 20)
- STT: 0.0125% on sell side only
- Exchange charges: ~0.002%
- GST: 18% on brokerage and exchange charges

### Position P&L Calculation
- Realized P&L: Locked in when closing/reducing position
- Unrealized P&L: Mark-to-market on current position
- Both update automatically as fills are applied

### Order State Machine
```
PENDING -> SUBMITTED -> ACKNOWLEDGED -> FILLED
                                     -> REJECTED
                     -> TIMEOUT (unknown fate)
```

### Grid Strategy Logic
```
Entry: RSI < 30 (oversold) -> Long
       RSI > 70 (overbought) -> Short

Pyramiding: Price moves favorable by (ATR * 1.5) -> Add level
            Limited to max_pyramid_levels

Stop: Price moves adverse by (ATR * 2.5) -> Exit all

Grid spacing adapts to volatility via ATR
```

## Implementation Notes

### Why Bar-Accurate Fills
You cannot execute on a bar's close price because that price has already happened. The earliest realistic execution is the next bar's open. This design enforces that constraint.

### Why Idempotency Matters
Network timeouts mean order fate is unknown. Blindly retrying creates risk of duplicate fills. Using client_order_id as an idempotency key makes retries safe.

### Why Separate Risk from Strategy
Strategies generate trading intent. Risk enforces constraints. This separation allows:
- Testing strategy logic independently
- Applying risk rules consistently across strategies
- Implementing emergency controls (kill switch) globally

## Status

Production-ready components:
- Both execution engines (Grid, Stop-and-Reverse)
- All technical indicator categories
- Risk management
- Order management with production patterns
- Backtesting with realistic costs
- 140 passing tests

Architecture ready but not implemented:
- Live broker API integration
- WebSocket real-time data
- Observability infrastructure
- Macro regime engine

## Running the Demo

The end-to-end demonstration shows:
1. Data generation (100 bars)
2. Indicator calculation (ATR, RSI)
3. Strategy signal generation (Grid)
4. Risk evaluation
5. Backtest execution with costs
6. Full P&L breakdown

```bash
python examples/grid_backtest_example.py
```

Output includes trade details, P&L breakdown, and system validation.

## License

Assessment code. All rights reserved.
