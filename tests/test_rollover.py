"""Tests for rollover manager."""

from datetime import date
from src.core.instrument import Instrument
from src.contracts.contract_master import ContractMaster
from src.contracts.rollover import RolloverManager


def _sample_contracts() -> list[Instrument]:
    """Create sample contracts for testing."""
    return [
        Instrument(symbol="NIFTY", exchange="NSE", lot_size=75, tick_size=0.05,
                   expiry=date(2026, 1, 30)),
        Instrument(symbol="NIFTY", exchange="NSE", lot_size=75, tick_size=0.05,
                   expiry=date(2026, 2, 27)),
        Instrument(symbol="NIFTY", exchange="NSE", lot_size=75, tick_size=0.05,
                   expiry=date(2026, 3, 26)),
    ]


def test_rollover_not_required_when_far_from_expiry():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    # Jan 15: 15 days until Jan 30 expiry
    decision = rm.check_rollover("NIFTY", date(2026, 1, 15))
    
    assert decision.required is False
    assert decision.current_symbol == "NIFTY_20260130"
    assert decision.next_symbol is None
    assert "not_near" in decision.reason or ">" in decision.reason


def test_rollover_required_within_window():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    # Jan 28: 2 days until Jan 30 expiry (within 3-day window)
    decision = rm.check_rollover("NIFTY", date(2026, 1, 28))
    
    assert decision.required is True
    assert decision.current_symbol == "NIFTY_20260130"
    assert decision.next_symbol == "NIFTY_20260227"
    assert "within_window" in decision.reason


def test_rollover_required_on_expiry_day():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    # Jan 30: expiry day itself (0 days, within window)
    decision = rm.check_rollover("NIFTY", date(2026, 1, 30))
    
    assert decision.required is True
    assert decision.next_symbol == "NIFTY_20260227"


def test_rollover_with_custom_window():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=7)
    
    # Jan 25: 5 days until expiry, within 7-day window
    decision = rm.check_rollover("NIFTY", date(2026, 1, 25))
    
    assert decision.required is True
    assert decision.next_symbol == "NIFTY_20260227"


def test_rollover_not_required_outside_custom_window():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=7)
    
    # Jan 22: 8 days until expiry, outside 7-day window
    decision = rm.check_rollover("NIFTY", date(2026, 1, 22))
    
    assert decision.required is False


def test_rollover_required_but_no_next_contract():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    # Mar 25: 1 day until Mar 26 expiry, but no next contract
    decision = rm.check_rollover("NIFTY", date(2026, 3, 25))
    
    assert decision.required is True
    assert decision.current_symbol == "NIFTY_20260326"
    assert decision.next_symbol is None
    assert "no_next" in decision.reason


def test_no_rollover_when_no_active_contract():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    # After all contracts expired
    decision = rm.check_rollover("NIFTY", date(2027, 1, 1))
    
    assert decision.required is False
    assert decision.current_symbol is None
    assert decision.next_symbol is None
    assert "no_active" in decision.reason


def test_no_rollover_for_unknown_symbol():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    decision = rm.check_rollover("UNKNOWN", date(2026, 1, 15))
    
    assert decision.required is False
    assert decision.current_symbol is None


def test_rollover_transitions_correctly_across_months():
    cm = ContractMaster(_sample_contracts())
    rm = RolloverManager(cm, rollover_days=3)
    
    # Feb 25: 2 days until Feb 27 expiry
    decision = rm.check_rollover("NIFTY", date(2026, 2, 25))
    
    assert decision.required is True
    assert decision.current_symbol == "NIFTY_20260227"
    assert decision.next_symbol == "NIFTY_20260326"
