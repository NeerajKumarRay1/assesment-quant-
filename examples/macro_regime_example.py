"""Demonstration of macro regime engine with various market conditions."""

from datetime import datetime, UTC
from src.macro.regime import MacroSnapshot, Regime
from src.macro.config import MacroRegimeConfig, RegimeParameters
from src.macro.engine import MacroRegimeEngine


def print_decision(title: str, snapshot: MacroSnapshot, decision):
    """Pretty print a regime decision."""
    print(f"\n{title}")
    print("=" * 70)
    print(f"Macro Snapshot:")
    print(f"  Timestamp:  {snapshot.timestamp}")
    print(f"  Volatility: {snapshot.volatility:.2f}")
    print(f"  Trend:      {snapshot.trend:+.2f}")
    print(f"  Sentiment:  {snapshot.sentiment:+.2f}")
    print(f"\nRegime Decision:")
    print(f"  Score:      {decision.score:+.3f}")
    print(f"  Regime:     {decision.regime.value}")
    print(f"\nStrategy Parameters:")
    print(f"  Grid spacing multiplier: {decision.parameters['grid_spacing_multiplier']:.1f}x")
    print(f"  Max pyramid levels:      {decision.parameters['max_pyramid_levels']}")
    print(f"  Stop loss multiplier:    {decision.parameters['stop_loss_multiplier']:.1f}x")
    print(f"\nCircuit Breaker:")
    if decision.circuit_breaker_active:
        print(f"  Status: ACTIVE ⚠️")
        print(f"  Reason: {decision.circuit_breaker_reason}")
    else:
        print(f"  Status: INACTIVE ✓")


def main():
    print("=" * 70)
    print("MACRO REGIME ENGINE DEMONSTRATION")
    print("=" * 70)
    
    # Create engine with default configuration
    config = MacroRegimeConfig(
        trend_weight=0.4,
        volatility_weight=0.3,
        sentiment_weight=0.3,
        risk_on_threshold=0.3,
        risk_off_threshold=-0.3,
        volatility_circuit_breaker_threshold=2.5,
        risk_on_params=RegimeParameters(
            grid_spacing_multiplier=1.0,
            max_pyramid_levels=3,
            stop_loss_multiplier=2.0
        ),
        neutral_params=RegimeParameters(
            grid_spacing_multiplier=1.5,
            max_pyramid_levels=2,
            stop_loss_multiplier=2.5
        ),
        risk_off_params=RegimeParameters(
            grid_spacing_multiplier=2.0,
            max_pyramid_levels=1,
            stop_loss_multiplier=3.0
        )
    )
    
    engine = MacroRegimeEngine(config)
    
    # Scenario 1: RISK_ON - Bull market conditions
    snapshot_risk_on = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=0.4,   # Low volatility
        trend=0.8,        # Strong bullish trend
        sentiment=0.7     # Positive sentiment (greed)
    )
    decision_risk_on = engine.evaluate(snapshot_risk_on)
    print_decision("Scenario 1: RISK_ON - Bull Market", snapshot_risk_on, decision_risk_on)
    
    # Scenario 2: NEUTRAL - Mixed signals
    snapshot_neutral = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
        volatility=0.8,   # Moderate volatility
        trend=0.2,        # Slight bullish
        sentiment=-0.1    # Slightly fearful
    )
    decision_neutral = engine.evaluate(snapshot_neutral)
    print_decision("Scenario 2: NEUTRAL - Mixed Signals", snapshot_neutral, decision_neutral)
    
    # Scenario 3: RISK_OFF - Bear market conditions
    snapshot_risk_off = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 11, 30, tzinfo=UTC),
        volatility=1.8,   # High volatility
        trend=-0.7,       # Strong bearish trend
        sentiment=-0.6    # Negative sentiment (fear)
    )
    decision_risk_off = engine.evaluate(snapshot_risk_off)
    print_decision("Scenario 3: RISK_OFF - Bear Market", snapshot_risk_off, decision_risk_off)
    
    # Scenario 4: Extreme volatility with circuit breaker
    snapshot_extreme = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        volatility=3.5,   # Extreme volatility (above 2.5 threshold)
        trend=-0.8,       # Sharp decline
        sentiment=-0.9    # Panic
    )
    decision_extreme = engine.evaluate(snapshot_extreme)
    print_decision("Scenario 4: EXTREME - Circuit Breaker Triggered", snapshot_extreme, decision_extreme)
    
    # Summary
    print("\n" + "=" * 70)
    print("ARCHITECTURE NOTES")
    print("=" * 70)
    print("""
The macro regime engine operates as follows:

1. INPUT: MacroSnapshot with volatility, trend, and sentiment proxies

2. SCORING: Weighted combination of normalized indicators
   - Positive contributors: trend, sentiment
   - Negative contributor: volatility
   - Formula: score = w1*trend - w2*volatility + w3*sentiment

3. CLASSIFICATION: Score mapped to regime using thresholds
   - score >= +0.3 → RISK_ON (aggressive parameters)
   - score <= -0.3 → RISK_OFF (conservative parameters)
   - between     → NEUTRAL (moderate parameters)

4. CIRCUIT BREAKER: Extreme volatility triggers safety mechanism
   - volatility >= 2.5 → circuit breaker ACTIVE
   - Blocks new risk-increasing positions via RiskManager
   - Allows risk-reducing positions (no forced liquidation)

5. PARAMETER OVERRIDES: Each regime modifies strategy behavior
   - RISK_ON:   Tight grids (1.0x), max pyramiding (3 levels)
   - NEUTRAL:   Medium grids (1.5x), limited pyramiding (2 levels)
   - RISK_OFF:  Wide grids (2.0x), minimal pyramiding (1 level)

6. INTEGRATION: Decisions flow to downstream components
   - Strategy uses parameter overrides
   - RiskManager enforces circuit breaker constraints
   - No automatic position liquidation

This demonstrates the separation of concerns:
- Macro engine: classifies environment and suggests parameters
- Strategy: decides what to trade based on signals
- RiskManager: enforces constraints and limits
- OrderManager: executes approved trades

The engine is deterministic, testable, and requires no live APIs.
""")
    print("=" * 70)


if __name__ == "__main__":
    main()
