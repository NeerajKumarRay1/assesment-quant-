"""Tests for contract master registry."""

from datetime import date
from src.core.instrument import Instrument
from src.contracts.contract_master import ContractMaster


def _sample_contracts() -> list[Instrument]:
    """Create sample contracts for testing."""
    return [
        Instrument(symbol="NIFTY", exchange="NSE", lot_size=75, tick_size=0.05, 
                   expiry=date(2026, 1, 30)),
        Instrument(symbol="NIFTY", exchange="NSE", lot_size=75, tick_size=0.05, 
                   expiry=date(2026, 2, 27)),
        Instrument(symbol="NIFTY", exchange="NSE", lot_size=75, tick_size=0.05, 
                   expiry=date(2026, 3, 26)),
        Instrument(symbol="BANKNIFTY", exchange="NSE", lot_size=25, tick_size=0.05, 
                   expiry=date(2026, 1, 28)),
        Instrument(symbol="BANKNIFTY", exchange="NSE", lot_size=25, tick_size=0.05, 
                   expiry=date(2026, 2, 25)),
    ]


def test_get_contract_returns_exact_match():
    cm = ContractMaster(_sample_contracts())
    contract = cm.get_contract("NIFTY", date(2026, 1, 30))
    assert contract is not None
    assert contract.symbol == "NIFTY"
    assert contract.expiry == date(2026, 1, 30)
    assert contract.lot_size == 75


def test_get_contract_returns_none_for_unknown():
    cm = ContractMaster(_sample_contracts())
    assert cm.get_contract("NIFTY", date(2026, 12, 31)) is None
    assert cm.get_contract("UNKNOWN", date(2026, 1, 30)) is None


def test_get_current_contract_returns_nearest_unexpired():
    cm = ContractMaster(_sample_contracts())
    # On Jan 15, the Jan 30 contract should be current
    current = cm.get_current_contract("NIFTY", date(2026, 1, 15))
    assert current is not None
    assert current.expiry == date(2026, 1, 30)


def test_get_current_contract_after_expiry_returns_next():
    cm = ContractMaster(_sample_contracts())
    # On Feb 1, Jan contract has expired, Feb should be current
    current = cm.get_current_contract("NIFTY", date(2026, 2, 1))
    assert current is not None
    assert current.expiry == date(2026, 2, 27)


def test_get_current_contract_returns_none_when_all_expired():
    cm = ContractMaster(_sample_contracts())
    # After all contracts expired
    current = cm.get_current_contract("NIFTY", date(2027, 1, 1))
    assert current is None


def test_get_next_contract_returns_subsequent_expiry():
    cm = ContractMaster(_sample_contracts())
    next_contract = cm.get_next_contract("NIFTY", date(2026, 1, 15))
    assert next_contract is not None
    assert next_contract.expiry == date(2026, 2, 27)


def test_get_next_contract_returns_none_when_no_next_exists():
    cm = ContractMaster(_sample_contracts())
    # On Mar 1, Mar is current, no next exists
    next_contract = cm.get_next_contract("NIFTY", date(2026, 3, 1))
    assert next_contract is None


def test_get_next_contract_returns_none_when_no_current():
    cm = ContractMaster(_sample_contracts())
    next_contract = cm.get_next_contract("UNKNOWN", date(2026, 1, 15))
    assert next_contract is None


def test_list_contracts_returns_sorted_by_expiry():
    cm = ContractMaster(_sample_contracts())
    contracts = cm.list_contracts("NIFTY")
    assert len(contracts) == 3
    assert contracts[0].expiry == date(2026, 1, 30)
    assert contracts[1].expiry == date(2026, 2, 27)
    assert contracts[2].expiry == date(2026, 3, 26)


def test_list_contracts_returns_empty_for_unknown_symbol():
    cm = ContractMaster(_sample_contracts())
    contracts = cm.list_contracts("UNKNOWN")
    assert contracts == []


def test_different_symbols_maintained_separately():
    cm = ContractMaster(_sample_contracts())
    nifty_contracts = cm.list_contracts("NIFTY")
    banknifty_contracts = cm.list_contracts("BANKNIFTY")
    assert len(nifty_contracts) == 3
    assert len(banknifty_contracts) == 2
    assert all(c.symbol == "NIFTY" for c in nifty_contracts)
    assert all(c.symbol == "BANKNIFTY" for c in banknifty_contracts)
