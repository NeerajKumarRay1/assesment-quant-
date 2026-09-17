# Quantitative Trading System

A production-grade algorithmic trading system implementing Grid and Stop-and-Reverse strategies with comprehensive risk management and realistic backtesting.

## Quick Start

```bash
# Install dependencies
pip install -e .[dev]

# Run tests
python -m pytest

# Run demonstrations
python examples/grid_backtest_example.py
python examples/async_feed_example.py
python examples/macro_regime_example.py
```

## Architecture

The system follows a layered architecture with clear separation of concerns:

```
Replay/Mock Data
       |
       v
 Async Producer
       |
       v
 Bounded Queue (back-pressure)
       |
       v
 Consumer
       |
       v
 Indicators -> Strategy <- Macro Regime (parameter overrides)
                  |              |
                  v              v (circuit breaker)
            Risk Manager
                  |
                  v
            Order Manager
                  |
                  v
               Broker
                  |
                Fills
                  |
              Position
                  |
                 P&L
```

### Market Data and Broker Environment

The system is broker-agnostic and designed for clean separation between data sources and trading logic:

1. **Mock/Replay Data**: Assessment uses deterministic mock and CSV replay data - no live credentials required
2. **Async Queue Boundary**: The bounded `asyncio.Queue` models the interface where a real WebSocket feed would connect
3. **Back-Pressure**: Queue size limits prevent unbounded memory growth during data bursts
4. **Graceful Shutdown**: Producer and consumer coordinate cleanly without leaving tasks running
5. **Broker Interface**: Abstract base allows plugging in real broker implementations (e.g., Zerodha Kite Connect) later

The async queue architecture demonstrates production patterns for handling real-time market data without requiring actual broker API access during development and testing.

## Observability and Reconciliation

Phase 3 adds a comprehensive observability layer providing structured logging, trade blotters, and reconciliation:

### Structured Logging
- **JSON event logging**: Machine-readable logs with consistent schema
- **Event types**: ORDER_SUBMITTED, ORDER_FILLED, ORDER_REJECTED, POSITION_CHANGED, RISK_REJECTED, CIRCUIT_BREAKER_TRIGGERED, RECONCILIATION_MISMATCH, etc.
- **Log levels**: Automatic level assignment (INFO for fills, WARNING for rejections, ERROR for mismatches)
- **Security**: Sensitive fields (tokens, passwords) automatically filtered

### Trade Blotter
- **Canonical record**: CSV-backed blotter records all executed trades
- **Idempotency**: Uses fill_id to prevent duplicate records
- **Audit trail**: Includes timestamp, instrument, side, quantity, price, strategy, costs, realized P&L
- **Persistence**: Survives restarts, provides complete trading history

### Position Reconciliation
- **Internal vs Broker**: Compares internal position tracking against broker positions
- **Mismatch detection**: Identifies quantity differences by symbol
- **Missing/extra symbols**: Detects positions that exist in one source but not the other
- **Reporting**: Generates detailed reconciliation reports with status indicators

### P&L Reconciliation
- **Tolerance-based**: Configurable floating-point tolerance for P&L comparison
- **Backtest vs Live**: Reconcile backtest results against live/broker P&L
- **Blotter reconciliation**: Compare any P&L calculation against canonical blotter records
- **Precision**: Handles floating-point arithmetic correctly

### Alert Abstraction
- **AlertSink protocol**: Clean interface for notification systems
- **Implementations**: LoggingAlertSink (for assessment), CollectingAlertSink (for tests)
- **Extension ready**: Can plug in SMS, Telegram, Slack, or email providers
- **Trigger criteria**: Alerts on position mismatches, material P&L differences, circuit breakers, engine errors

### Integration
The observability layer integrates as a separate cross-cutting concern:
- **Minimal coupling**: Core domain objects (Position, Order, Fill) remain unchanged
- **Dependency injection**: Observability components injected at application boundaries
- **Optional**: Existing code works without observability (backward compatible)
- **Event boundaries**: Events emitted from OrderManager, RiskManager, MacroRegimeEngine

### Reconciliation Flow
```
Trading Engine → Internal Position State
                       |
                       ↓
               [Reconciliation]
                       |
          +------------+------------+
          |                         |
    Broker Positions          Expected P&L
          |                         |
          ↓                         ↓
      [Compare]               [Compare]
          |                         |
    ✓ MATCH / ✗ MISMATCH      ✓ MATCH / ✗ MISMATCH
          |                         |
          +------------+------------+
                       |
                       ↓
                  🚨 ALERT (if mismatch)
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
- ReplayMarketData: CSV-based deterministic replay feed for testing
- AsyncMarketDataFeed: Asynchronous producer/consumer pipeline with back-pressure

### Contract Management
Derivative instrument lifecycle:
- ContractMaster: Registry of contracts with expiry information
- RolloverManager: Determines when to roll contracts based on expiry windows
- Expiry handling: Explicit contract transitions, no silent rollovers

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
- Circuit breaker integration (from macro regime)
- Risk decisions with rejection reasons

### Macro Regime Engine
Market environment classification and parameter adaptation:
- **Regime Classification**: RISK_ON, NEUTRAL, RISK_OFF based on macro indicators
- **Macro Inputs**: Volatility, trend, sentiment proxies (deterministic, no live APIs)
- **Scoring System**: Weighted combination of normalized indicators
- **Parameter Overrides**: Regime-specific strategy parameters (grid spacing, pyramid levels, stops)
- **Circuit Breaker**: Extreme volatility blocks risk-increasing positions
- **Integration**: Flows to RiskManager without replacing it

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

### Macro Regime Engine
The system adapts to market conditions through deterministic regime classification. Macro indicators (volatility, trend, sentiment) are weighted and scored to classify the environment as RISK_ON, NEUTRAL, or RISK_OFF. Each regime applies different strategy parameters (grid spacing, pyramid levels, stop distances). Extreme volatility triggers a circuit breaker that blocks new risk-increasing positions through the RiskManager, but does not force liquidation of existing positions. The engine is fully deterministic and requires no live APIs - it operates on normalized indicator proxies.

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
├── core/           # Domain objects (Order, Position, Fill, Instrument, etc.)
├── contracts/      # Contract master and rollover management
├── broker/         # Broker abstraction and MockBroker
├── market_data/    # Market data: Mock, Replay, Async feeds
├── indicators/     # Technical indicators (ATR, RSI, EMA, OBV)
├── strategy/       # Trading strategies (Grid, Stop-and-Reverse)
├── risk/           # Risk management
├── macro/          # Macro regime engine
├── execution/      # Order manager
├── backtest/       # Backtesting engine
└── observability/  # Logging, blotter, reconciliation, alerts (NEW)

data/               # Sample CSV data for replay
tests/              # 270+ tests
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

**Complete and Production-Ready:**
- ✅ Both execution engines (Grid, Stop-and-Reverse)
- ✅ All technical indicator categories (ATR, RSI, EMA, OBV)
- ✅ Risk management with circuit breaker integration
- ✅ Macro regime engine with parameter adaptation
- ✅ Order management with idempotency and reconciliation
- ✅ Contract master and rollover management
- ✅ Replay and async market data feeds with back-pressure
- ✅ Backtesting with realistic costs and slippage
- ✅ Observability layer with structured logging, trade blotter, reconciliation, alerts
- ✅ **276 passing tests**

**Architecture Demonstrated (Partial):**
- ⚠️ Broker resilience utilities (retry with exponential backoff, auth abstraction, rate limiting)
- ⚠️ Note: These are utility components demonstrating the architecture; not integrated with mock broker

**Not Required for Mock Environment:**
- Live Zerodha broker API integration
- WebSocket connectivity
- External notification systems (SMS/Telegram/Slack)

## Running the Demo

The end-to-end demonstrations show:

**Grid Backtest:**
```bash
python examples/grid_backtest_example.py
```
1. Data generation (100 bars)
2. Indicator calculation (ATR, RSI)
3. Strategy signal generation (Grid)
4. Risk evaluation
5. Backtest execution with costs
6. Full P&L breakdown

**Observability:**
```bash
python examples/observability_example.py
```
1. Structured JSON logging of trading events
2. Trade blotter recording with idempotency
3. Position reconciliation (matching & mismatch)
4. P&L reconciliation with tolerance
5. Alert generation on mismatches
6. Complete reconciliation reports

## License

Assessment code. All rights reserved.
