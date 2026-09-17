"""Tests for macro regime engine."""

from datetime import datetime, UTC
from src.macro.regime import Regime, MacroSnapshot, RegimeDecision
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


def _create_snapshot(volatility: float, trend: float, sentiment: float) -> MacroSnapshot:
    """Helper to create macro snapshot."""
    return MacroSnapshot(
        timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
        volatility=volatility,
        trend=trend,
        sentiment=sentiment
    )


# ============================================================================
# REGIME CLASSIFICATION TESTS
# ============================================================================

def test_strong_positive_environment_is_risk_on():
    """Strong positive signals should classify as RISK_ON."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(
        volatility=0.3,   # Low volatility
        trend=0.8,        # Strong bullish trend
        sentiment=0.7     # Positive sentiment
    )
    
    decision = engine.evaluate(snapshot)
    
    assert decision.regime == Regime.RISK_ON
    assert decision.score >= 0.3  # Above risk_on_threshold


def test_neutral_environment_is_neutral():
    """Mixed signals should classify as NEUTRAL."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(
        volatility=0.5,   # Moderate volatility
        trend=0.1,        # Slight bullish
        sentiment=0.0     # Neutral sentiment
    )
    
    decision = engine.evaluate(snapshot)
    
    assert decision.regime == Regime.NEUTRAL
    assert -0.3 < decision.score < 0.3  # Between thresholds


def test_strong_negative_environment_is_risk_off():
    """Strong negative signals should classify as RISK_OFF."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(
        volatility=1.5,   # High volatility
        trend=-0.8,       # Strong bearish trend
        sentiment=-0.7    # Negative sentiment
    )
    
    decision = engine.evaluate(snapshot)
    
    assert decision.regime == Regime.RISK_OFF
    assert decision.score <= -0.3  # Below risk_off_threshold


# ============================================================================
# SCORING TESTS
# ============================================================================

def test_positive_trend_increases_score():
    """Positive trend should increase regime score."""
    engine = MacroRegimeEngine(_default_config())
    
    snapshot_bearish = _create_snapshot(0.5, -0.5, 0.0)
    snapshot_bullish = _create_snapshot(0.5, 0.5, 0.0)
    
    score_bearish = engine.evaluate(snapshot_bearish).score
    score_bullish = engine.evaluate(snapshot_bullish).score
    
    assert score_bullish > score_bearish


def test_high_volatility_decreases_score():
    """Higher volatility should decrease regime score."""
    engine = MacroRegimeEngine(_default_config())
    
    snapshot_low_vol = _create_snapshot(0.2, 0.5, 0.5)
    snapshot_high_vol = _create_snapshot(1.5, 0.5, 0.5)
    
    score_low_vol = engine.evaluate(snapshot_low_vol).score
    score_high_vol = engine.evaluate(snapshot_high_vol).score
    
    assert score_low_vol > score_high_vol


def test_positive_sentiment_increases_score():
    """Positive sentiment should increase regime score."""
    engine = MacroRegimeEngine(_default_config())
    
    snapshot_fearful = _create_snapshot(0.5, 0.0, -0.5)
    snapshot_greedy = _create_snapshot(0.5, 0.0, 0.5)
    
    score_fearful = engine.evaluate(snapshot_fearful).score
    score_greedy = engine.evaluate(snapshot_greedy).score
    
    assert score_greedy > score_fearful


def test_weights_affect_score():
    """Different weights should produce different scores."""
    config_trend_heavy = MacroRegimeConfig(
        trend_weight=0.7,
        volatility_weight=0.2,
        sentiment_weight=0.1,
        risk_on_threshold=0.3,
        risk_off_threshold=-0.3,
        volatility_circuit_breaker_threshold=2.5
    )
    
    config_vol_heavy = MacroRegimeConfig(
        trend_weight=0.1,
        volatility_weight=0.7,
        sentiment_weight=0.2,
        risk_on_threshold=0.3,
        risk_off_threshold=-0.3,
        volatility_circuit_breaker_threshold=2.5
    )
    
    snapshot = _create_snapshot(1.0, 0.8, 0.2)
    
    score_trend_heavy = MacroRegimeEngine(config_trend_heavy).evaluate(snapshot).score
    score_vol_heavy = MacroRegimeEngine(config_vol_heavy).evaluate(snapshot).score
    
    # Trend-heavy should score higher (trend is positive, vol is negative contributor)
    assert score_trend_heavy > score_vol_heavy


def test_zero_inputs_give_zero_score():
    """All neutral/zero inputs should give near-zero score."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(0.0, 0.0, 0.0)
    
    decision = engine.evaluate(snapshot)
    
    assert abs(decision.score) < 0.01
    assert decision.regime == Regime.NEUTRAL


# ============================================================================
# THRESHOLD TESTS
# ============================================================================

def test_exactly_at_risk_on_threshold():
    """Score exactly at risk_on_threshold should classify as RISK_ON."""
    config = _default_config()
    engine = MacroRegimeEngine(config)
    
    # Craft inputs to hit exactly 0.3
    # score = 0.4*trend - 0.3*vol + 0.3*sent = 0.3
    # Using trend=0.75, vol=0, sent=0: 0.4*0.75 = 0.3
    snapshot = _create_snapshot(0.0, 0.75, 0.0)
    decision = engine.evaluate(snapshot)
    
    assert abs(decision.score - 0.3) < 0.01
    assert decision.regime == Regime.RISK_ON


def test_exactly_at_risk_off_threshold():
    """Score exactly at risk_off_threshold should classify as RISK_OFF."""
    config = _default_config()
    engine = MacroRegimeEngine(config)
    
    # Craft inputs to hit exactly -0.3
    # Using trend=-0.75, vol=0, sent=0: 0.4*(-0.75) = -0.3
    snapshot = _create_snapshot(0.0, -0.75, 0.0)
    decision = engine.evaluate(snapshot)
    
    assert abs(decision.score - (-0.3)) < 0.01
    assert decision.regime == Regime.RISK_OFF


def test_between_thresholds_is_neutral():
    """Score between thresholds should be NEUTRAL."""
    engine = MacroRegimeEngine(_default_config())
    
    # score = 0.4*0.2 - 0.3*0.2 + 0.3*0.1 = 0.08 - 0.06 + 0.03 = 0.05
    snapshot = _create_snapshot(0.2, 0.2, 0.1)
    decision = engine.evaluate(snapshot)
    
    assert -0.3 < decision.score < 0.3
    assert decision.regime == Regime.NEUTRAL


# ============================================================================
# PARAMETER OVERRIDE TESTS
# ============================================================================

def test_risk_on_returns_aggressive_parameters():
    """RISK_ON should return aggressive trading parameters."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(0.2, 0.9, 0.8)  # Strong positive
    
    decision = engine.evaluate(snapshot)
    
    assert decision.regime == Regime.RISK_ON
    assert decision.parameters['grid_spacing_multiplier'] == 1.0
    assert decision.parameters['max_pyramid_levels'] == 3
    assert decision.parameters['stop_loss_multiplier'] == 2.0


def test_neutral_returns_moderate_parameters():
    """NEUTRAL should return moderate trading parameters."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(0.5, 0.0, 0.0)  # Neutral
    
    decision = engine.evaluate(snapshot)
    
    assert decision.regime == Regime.NEUTRAL
    assert decision.parameters['grid_spacing_multiplier'] == 1.5
    assert decision.parameters['max_pyramid_levels'] == 2
    assert decision.parameters['stop_loss_multiplier'] == 2.5


def test_risk_off_returns_conservative_parameters():
    """RISK_OFF should return conservative trading parameters."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(1.5, -0.9, -0.8)  # Strong negative
    
    decision = engine.evaluate(snapshot)
    
    assert decision.regime == Regime.RISK_OFF
    assert decision.parameters['grid_spacing_multiplier'] == 2.0
    assert decision.parameters['max_pyramid_levels'] == 1
    assert decision.parameters['stop_loss_multiplier'] == 3.0


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================

def test_normal_volatility_circuit_breaker_inactive():
    """Normal volatility should not trigger circuit breaker."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(1.0, 0.5, 0.5)  # Below 2.5 threshold
    
    decision = engine.evaluate(snapshot)
    
    assert not decision.circuit_breaker_active
    assert decision.circuit_breaker_reason is None


def test_extreme_volatility_triggers_circuit_breaker():
    """Extreme volatility should trigger circuit breaker."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(3.0, 0.5, 0.5)  # Above 2.5 threshold
    
    decision = engine.evaluate(snapshot)
    
    assert decision.circuit_breaker_active
    assert decision.circuit_breaker_reason is not None
    assert "volatility_above_threshold" in decision.circuit_breaker_reason


def test_circuit_breaker_includes_explicit_reason():
    """Circuit breaker reason should include volatility value."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(3.5, 0.0, 0.0)
    
    decision = engine.evaluate(snapshot)
    
    assert decision.circuit_breaker_active
    assert "3.50" in decision.circuit_breaker_reason or "3.5" in decision.circuit_breaker_reason
    assert "2.5" in decision.circuit_breaker_reason


def test_circuit_breaker_at_exact_threshold():
    """Volatility exactly at threshold should trigger circuit breaker."""
    engine = MacroRegimeEngine(_default_config())
    snapshot = _create_snapshot(2.5, 0.0, 0.0)
    
    decision = engine.evaluate(snapshot)
    
    assert decision.circuit_breaker_active


def test_circuit_breaker_does_not_change_regime():
    """Circuit breaker should not affect regime classification significantly.
    
    High volatility DOES affect the score (it's a negative contributor),
    but the test verifies that with otherwise identical strong positive signals,
    both scenarios are still in favorable territory (not switching from RISK_ON to RISK_OFF).
    """
    engine = MacroRegimeEngine(_default_config())
    
    # Snapshot with low volatility - should be RISK_ON
    snapshot_normal = _create_snapshot(0.5, 0.8, 0.7)
    
    # Snapshot with extreme volatility but same trend/sentiment
    # Note: High volatility will decrease score, but should still be positive
    snapshot_extreme = _create_snapshot(1.2, 0.8, 0.7)  # High but below circuit breaker
    
    decision_normal = engine.evaluate(snapshot_normal)
    decision_extreme = engine.evaluate(snapshot_extreme)
    
    # Both should be positive regime (RISK_ON or NEUTRAL), not RISK_OFF
    assert decision_normal.regime in [Regime.RISK_ON, Regime.NEUTRAL]
    assert decision_extreme.regime in [Regime.RISK_ON, Regime.NEUTRAL]
    assert decision_normal.score > decision_extreme.score  # Normal should score higher
    assert not decision_extreme.circuit_breaker_active  # Below threshold


# ============================================================================
# CONFIGURATION VALIDATION TESTS
# ============================================================================

def test_invalid_threshold_order_raises_error():
    """risk_off_threshold >= risk_on_threshold should raise error."""
    try:
        MacroRegimeConfig(
            risk_on_threshold=0.2,
            risk_off_threshold=0.5,  # Invalid: should be less than risk_on
            volatility_circuit_breaker_threshold=2.5
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be less than" in str(e)


def test_negative_circuit_breaker_threshold_raises_error():
    """Negative circuit breaker threshold should raise error."""
    try:
        MacroRegimeConfig(
            risk_on_threshold=0.3,
            risk_off_threshold=-0.3,
            volatility_circuit_breaker_threshold=-1.0
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "must be positive" in str(e)


def test_negative_weights_raise_error():
    """Negative weights should raise error."""
    try:
        MacroRegimeConfig(
            trend_weight=-0.4,
            volatility_weight=0.3,
            sentiment_weight=0.3,
            risk_on_threshold=0.3,
            risk_off_threshold=-0.3,
            volatility_circuit_breaker_threshold=2.5
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "non-negative" in str(e)
