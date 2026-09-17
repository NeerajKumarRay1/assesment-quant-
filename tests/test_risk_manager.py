"""Tests for risk management layer."""

import pytest
from src.risk import RiskManager, RiskDecision
from src.core.position import Position


def test_risk_allows_position_within_cap():
    """Strategy wants +3, cap is +5, currently flat → should allow +3."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=3,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 3
    assert decision.rejection_reason is None


def test_risk_enforces_long_position_cap():
    """Strategy wants +7, cap is +5 → should cap to +5."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=7,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 5
    assert "capped" in decision.rejection_reason.lower()


def test_risk_enforces_short_position_cap():
    """Strategy wants -8, cap is 5 (symmetric) → should cap to -5."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=-8,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == -5
    assert "capped" in decision.rejection_reason.lower()


def test_risk_allows_position_at_exact_cap():
    """Strategy wants exactly +5, cap is +5 → should allow."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=5,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 5
    assert decision.rejection_reason is None


def test_risk_prevents_exceeding_cap_from_existing_position():
    """Currently +3, wants +8, cap is +5 → should cap to +5 (can only add +2)."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=3)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=8,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 5


def test_risk_no_increase_when_already_at_cap():
    """Currently +5, wants +7, cap is +5 → should keep at +5."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=5)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=7,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 5


def test_kill_switch_blocks_new_exposure():
    """Kill switch active, currently flat, wants +5 → should reject."""
    risk = RiskManager(max_position=5, kill_switch=True)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=5,
        current_position=pos
    )
    
    assert decision.allowed is False
    assert decision.target_quantity == 0  # keep current
    assert "kill switch" in decision.rejection_reason.lower()


def test_kill_switch_allows_reducing_position():
    """Kill switch active, currently +5, wants +2 → should allow (reducing)."""
    risk = RiskManager(max_position=5, kill_switch=True)
    pos = Position(instrument="NIFTY", quantity=5)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=2,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 2
    # No rejection reason when reducing is allowed


def test_kill_switch_allows_flattening():
    """Kill switch active, currently +5, wants 0 → should allow (flattening)."""
    risk = RiskManager(max_position=5, kill_switch=True)
    pos = Position(instrument="NIFTY", quantity=5)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=0,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == 0


def test_kill_switch_rejects_increasing_position():
    """Kill switch active, currently +3, wants +5 → should reject."""
    risk = RiskManager(max_position=10, kill_switch=True)
    pos = Position(instrument="NIFTY", quantity=3)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=5,
        current_position=pos
    )
    
    assert decision.allowed is False
    assert decision.target_quantity == 3  # keep current


def test_kill_switch_blocks_increasing_short():
    """Kill switch active, currently -2, wants -5 → should reject."""
    risk = RiskManager(max_position=10, kill_switch=True)
    pos = Position(instrument="NIFTY", quantity=-2)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=-5,
        current_position=pos
    )
    
    assert decision.allowed is False
    assert decision.target_quantity == -2


def test_kill_switch_allows_reducing_short():
    """Kill switch active, currently -5, wants -2 → should allow."""
    risk = RiskManager(max_position=10, kill_switch=True)
    pos = Position(instrument="NIFTY", quantity=-5)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=-2,
        current_position=pos
    )
    
    assert decision.allowed is True
    assert decision.target_quantity == -2


def test_rejection_reason_provided_for_cap():
    """When capped, rejection_reason should explain what happened."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="NIFTY",
        desired_quantity=10,
        current_position=pos
    )
    
    assert decision.rejection_reason is not None
    assert "10" in decision.rejection_reason
    assert "5" in decision.rejection_reason


def test_instrument_mismatch_rejected():
    """Risk should reject if instrument doesn't match position."""
    risk = RiskManager(max_position=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    decision = risk.evaluate(
        instrument="BANKNIFTY",  # different instrument
        desired_quantity=3,
        current_position=pos
    )
    
    assert decision.allowed is False
    assert "mismatch" in decision.rejection_reason.lower()


def test_risk_manager_requires_positive_max_position():
    """RiskManager should reject non-positive max_position."""
    with pytest.raises(ValueError):
        RiskManager(max_position=0)
    
    with pytest.raises(ValueError):
        RiskManager(max_position=-5)


def test_risk_decision_is_frozen():
    """RiskDecision should be immutable."""
    import dataclasses
    decision = RiskDecision(allowed=True, target_quantity=5, rejection_reason=None)
    
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = False
