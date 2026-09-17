"""Integration tests for macro regime engine with risk management."""

from datetime import datetime, UTC
from src.core.position import Position
from src.core.order import Fill, Side
from src.risk.risk_manager import RiskManager
from src.macro.regime import MacroSnapshot
from src.macro.config import MacroRegimeConfig, RegimeParameters
from src.macro.engine import MacroRegimeEngine


def _default_config() -> MacroRegimeConfig:
    """Create default test configuration."""
    return MacroRegimeConfig(
        trend_weight=0.4,
        volatility_weight=0.3,
        sentiment_weight=0.3,
        risk_on_threshold=0.3,
        risk_off_threshold=-0.3,
        volatility_circuit_breaker_threshold=2.5,
        risk_on_params=RegimeParameters(1.0, 3, 2.0),
        neutral_params=RegimeParameters(1.5, 2, 2.5),
        risk_off_params=RegimeParameters(2.0, 1, 3.0)
    )


def test_macro_decision_flows_to_risk_layer():
    """Macro regime decision should integrate with risk manager."""
    engine = MacroRegimeEngine(_default_config())
    risk_mgr = RiskManager(max_position=5)
    
    # Create macro snapshot
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=0.5,
        trend=0.7,
        sentiment=0.6
    )
    
    # Evaluate macro regime
    macro_decision = engine.evaluate(snapshot)
    
    # Use macro decision in risk evaluation
    position = Position(instrument="NIFTY")
    risk_decision = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=3,
        current_position=position,
        circuit_breaker_active=macro_decision.circuit_breaker_active
    )
    
    # Should be allowed - no circuit breaker active
    assert risk_decision.allowed
    assert risk_decision.target_quantity == 3


def test_circuit_breaker_blocks_new_position():
    """Circuit breaker should block new risk-increasing positions."""
    engine = MacroRegimeEngine(_default_config())
    risk_mgr = RiskManager(max_position=5)
    
    # Create extreme volatility snapshot
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=3.0,  # Above threshold
        trend=0.5,
        sentiment=0.5
    )
    
    macro_decision = engine.evaluate(snapshot)
    assert macro_decision.circuit_breaker_active
    
    # Try to enter new position - should be blocked
    position = Position(instrument="NIFTY")
    risk_decision = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=3,
        current_position=position,
        circuit_breaker_active=macro_decision.circuit_breaker_active
    )
    
    assert not risk_decision.allowed
    assert "Circuit breaker active" in risk_decision.rejection_reason
    assert risk_decision.target_quantity == 0


def test_circuit_breaker_allows_position_reduction():
    """Circuit breaker should allow reducing existing positions."""
    engine = MacroRegimeEngine(_default_config())
    risk_mgr = RiskManager(max_position=5)
    
    # Create extreme volatility snapshot
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=3.5,
        trend=-0.8,
        sentiment=-0.7
    )
    
    macro_decision = engine.evaluate(snapshot)
    assert macro_decision.circuit_breaker_active
    
    # Have existing position of +5
    position = Position(instrument="NIFTY")
    position.apply_fill(Fill(
        order_id="test_1",
        instrument="NIFTY",
        side=Side.BUY,
        quantity=5,
        price=25000.0,
        filled_at=datetime(2026, 1, 15, tzinfo=UTC)
    ))
    
    # Try to reduce to +2 - should be allowed
    risk_decision = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=2,
        current_position=position,
        circuit_breaker_active=macro_decision.circuit_breaker_active
    )
    
    assert risk_decision.allowed
    assert risk_decision.target_quantity == 2


def test_circuit_breaker_blocks_position_increase():
    """Circuit breaker should block increasing existing positions."""
    engine = MacroRegimeEngine(_default_config())
    risk_mgr = RiskManager(max_position=5)
    
    # Create extreme volatility snapshot
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=4.0,
        trend=0.0,
        sentiment=0.0
    )
    
    macro_decision = engine.evaluate(snapshot)
    assert macro_decision.circuit_breaker_active
    
    # Have existing position of +2
    position = Position(instrument="NIFTY")
    position.apply_fill(Fill(
        order_id="test_1",
        instrument="NIFTY",
        side=Side.BUY,
        quantity=2,
        price=25000.0,
        filled_at=datetime(2026, 1, 15, tzinfo=UTC)
    ))
    
    # Try to increase to +5 - should be blocked
    risk_decision = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=5,
        current_position=position,
        circuit_breaker_active=macro_decision.circuit_breaker_active
    )
    
    assert not risk_decision.allowed
    assert "Circuit breaker active" in risk_decision.rejection_reason
    assert risk_decision.target_quantity == 2  # Stays at current


def test_circuit_breaker_allows_closing_position():
    """Circuit breaker should allow fully closing positions."""
    engine = MacroRegimeEngine(_default_config())
    risk_mgr = RiskManager(max_position=5)
    
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=3.0,
        trend=0.0,
        sentiment=0.0
    )
    
    macro_decision = engine.evaluate(snapshot)
    assert macro_decision.circuit_breaker_active
    
    # Have existing position of +3
    position = Position(instrument="NIFTY")
    position.apply_fill(Fill(
        order_id="test_1",
        instrument="NIFTY",
        side=Side.BUY,
        quantity=3,
        price=25000.0,
        filled_at=datetime(2026, 1, 15, tzinfo=UTC)
    ))
    
    # Try to close position - should be allowed
    risk_decision = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=0,
        current_position=position,
        circuit_breaker_active=macro_decision.circuit_breaker_active
    )
    
    assert risk_decision.allowed
    assert risk_decision.target_quantity == 0


def test_risk_on_regime_uses_aggressive_parameters():
    """RISK_ON regime should provide aggressive parameters for strategy."""
    engine = MacroRegimeEngine(_default_config())
    
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=0.3,
        trend=0.9,
        sentiment=0.8
    )
    
    decision = engine.evaluate(snapshot)
    
    from src.macro.regime import Regime
    assert decision.regime == Regime.RISK_ON
    assert decision.parameters['max_pyramid_levels'] == 3
    assert decision.parameters['grid_spacing_multiplier'] == 1.0


def test_risk_off_regime_uses_conservative_parameters():
    """RISK_OFF regime should provide conservative parameters for strategy."""
    engine = MacroRegimeEngine(_default_config())
    
    snapshot = MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=2.0,
        trend=-0.9,
        sentiment=-0.8
    )
    
    decision = engine.evaluate(snapshot)
    
    from src.macro.regime import Regime
    assert decision.regime == Regime.RISK_OFF
    assert decision.parameters['max_pyramid_levels'] == 1
    assert decision.parameters['grid_spacing_multiplier'] == 2.0


def test_kill_switch_and_circuit_breaker_both_block():
    """Both kill switch and circuit breaker should block new exposure."""
    risk_mgr = RiskManager(max_position=5, kill_switch=True)
    
    position = Position(instrument="NIFTY")
    
    # Circuit breaker alone
    risk_decision_cb = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=3,
        current_position=position,
        circuit_breaker_active=True
    )
    assert not risk_decision_cb.allowed
    
    # Kill switch alone (circuit_breaker_active defaults to False)
    risk_decision_ks = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=3,
        current_position=position
    )
    assert not risk_decision_ks.allowed


def test_circuit_breaker_checked_before_kill_switch():
    """Circuit breaker should be checked first (order matters for error messages)."""
    risk_mgr = RiskManager(max_position=5, kill_switch=True)
    
    position = Position(instrument="NIFTY")
    
    risk_decision = risk_mgr.evaluate(
        instrument="NIFTY",
        desired_quantity=3,
        current_position=position,
        circuit_breaker_active=True
    )
    
    assert not risk_decision.allowed
    # Circuit breaker message should appear (it's checked first)
    assert "Circuit breaker" in risk_decision.rejection_reason
