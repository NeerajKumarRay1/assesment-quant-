"""Integration tests for Phase 1: Contract master, rollover, and replay feed."""

from datetime import date
from pathlib import Path
from src.core.instrument import Instrument
from src.contracts.contract_master import ContractMaster
from src.contracts.rollover import RolloverManager
from src.market_data.replay_market_data import ReplayMarketData


def test_contract_master_with_rollover_decision():
    """Integration: Contract master provides data for rollover decisions."""
    contracts = [
        Instrument("NIFTY", "NSE", 75, 0.05, date(2026, 1, 30)),
        Instrument("NIFTY", "NSE", 75, 0.05, date(2026, 2, 27)),
    ]
    
    cm = ContractMaster(contracts)
    rm = RolloverManager(cm, rollover_days=5)
    
    # Early in month - no rollover
    decision = rm.check_rollover("NIFTY", date(2026, 1, 15))
    assert not decision.required
    assert decision.current_symbol == "NIFTY_20260130"
    
    # Near expiry - rollover required
    decision = rm.check_rollover("NIFTY", date(2026, 1, 26))
    assert decision.required
    assert decision.next_symbol == "NIFTY_20260227"


def test_replay_feed_loads_and_streams():
    """Integration: Replay feed successfully loads CSV and streams ticks."""
    csv_path = Path("data/sample_ticks.csv")
    feed = ReplayMarketData(csv_path)
    
    # Check instruments detected
    instruments = feed.get_instruments()
    assert "NIFTY" in instruments
    assert "BANKNIFTY" in instruments
    
    # Stream NIFTY ticks
    nifty_ticks = list(feed.stream_ticks("NIFTY"))
    assert len(nifty_ticks) > 0
    assert all(t.instrument == "NIFTY" for t in nifty_ticks)
    assert all(t.price > 0 for t in nifty_ticks)
    
    # Stream all ticks
    all_ticks = list(feed.stream_all_ticks())
    assert len(all_ticks) >= len(nifty_ticks)


def test_replay_feed_with_contract_master():
    """Integration: Use replay feed with contract information."""
    # Set up contracts
    contracts = [
        Instrument("NIFTY", "NSE", 75, 0.05, date(2026, 1, 30)),
    ]
    cm = ContractMaster(contracts)
    
    # Load replay data
    csv_path = Path("data/sample_ticks.csv")
    feed = ReplayMarketData(csv_path)
    
    # Get contract for instrument
    contract = cm.get_contract("NIFTY", date(2026, 1, 30))
    assert contract is not None
    assert contract.lot_size == 75
    
    # Verify we can stream ticks for this instrument
    ticks = list(feed.stream_ticks(contract.symbol))
    assert len(ticks) > 0
    
    # Calculate notional value using contract lot size
    first_tick = ticks[0]
    notional = first_tick.price * contract.lot_size
    assert notional > 0


def test_rollover_decision_informs_which_contract_to_trade():
    """Integration: Rollover manager helps select active contract."""
    contracts = [
        Instrument("NIFTY", "NSE", 75, 0.05, date(2026, 1, 30)),
        Instrument("NIFTY", "NSE", 75, 0.05, date(2026, 2, 27)),
        Instrument("NIFTY", "NSE", 75, 0.05, date(2026, 3, 26)),
    ]
    
    cm = ContractMaster(contracts)
    rm = RolloverManager(cm, rollover_days=3)
    
    # Scenario: Trading on Jan 28, need to decide which contract
    trading_date = date(2026, 1, 28)
    
    # Check if rollover is needed
    decision = rm.check_rollover("NIFTY", trading_date)
    
    if decision.required and decision.next_symbol:
        # Should trade next contract
        assert decision.next_symbol == "NIFTY_20260227"
        next_contract = cm.get_next_contract("NIFTY", trading_date)
        assert next_contract is not None
        assert next_contract.expiry == date(2026, 2, 27)
    else:
        # Should trade current contract
        current_contract = cm.get_current_contract("NIFTY", trading_date)
        assert current_contract is not None
