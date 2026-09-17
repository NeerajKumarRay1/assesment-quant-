"""Tests for position and P&L reconciliation."""

from src.core.position import Position
from src.observability.reconciliation import (
    reconcile_positions,
    reconcile_pnl,
    format_reconciliation_report,
    create_reconciliation_report,
)


def test_matching_positions():
    """Reconciliation passes when positions match."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50),
        "BANKNIFTY": Position("BANKNIFTY", quantity=-25)
    }
    
    broker = {
        "NIFTY": 50,
        "BANKNIFTY": -25
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is True
    assert len(result.position_mismatches) == 2
    assert not result.has_position_mismatches()


def test_mismatched_positions():
    """Reconciliation fails when positions don't match."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50)
    }
    
    broker = {
        "NIFTY": 25  # Mismatch!
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is False
    assert result.has_position_mismatches()
    assert len(result.position_mismatches) == 1
    
    mismatch = result.position_mismatches[0]
    assert mismatch.symbol == "NIFTY"
    assert mismatch.expected_quantity == 50
    assert mismatch.actual_quantity == 25
    assert mismatch.difference == -25


def test_missing_symbol_in_broker():
    """Reconciliation detects symbols missing from broker."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50),
        "BANKNIFTY": Position("BANKNIFTY", quantity=25)
    }
    
    broker = {
        "NIFTY": 50
        # BANKNIFTY missing
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is False
    assert result.has_position_mismatches()
    
    # Find BANKNIFTY mismatch
    banknifty_mismatch = next(
        m for m in result.position_mismatches if m.symbol == "BANKNIFTY"
    )
    assert banknifty_mismatch.expected_quantity == 25
    assert banknifty_mismatch.actual_quantity == 0
    assert banknifty_mismatch.difference == -25


def test_extra_symbol_in_broker():
    """Reconciliation detects extra symbols in broker."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50)
    }
    
    broker = {
        "NIFTY": 50,
        "BANKNIFTY": 25  # Extra position!
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is False
    assert result.has_position_mismatches()
    
    # Find BANKNIFTY mismatch
    banknifty_mismatch = next(
        m for m in result.position_mismatches if m.symbol == "BANKNIFTY"
    )
    assert banknifty_mismatch.expected_quantity == 0
    assert banknifty_mismatch.actual_quantity == 25
    assert banknifty_mismatch.difference == 25


def test_multiple_mismatches():
    """Reconciliation handles multiple mismatches."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50),
        "BANKNIFTY": Position("BANKNIFTY", quantity=-25),
        "FINNIFTY": Position("FINNIFTY", quantity=10)
    }
    
    broker = {
        "NIFTY": 25,        # Wrong
        "BANKNIFTY": -25,   # Correct
        "FINNIFTY": 20      # Wrong
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is False
    assert result.has_position_mismatches()
    
    mismatched_symbols = result.get_mismatched_symbols()
    assert "NIFTY" in mismatched_symbols
    assert "FINNIFTY" in mismatched_symbols
    assert "BANKNIFTY" not in mismatched_symbols


def test_pnl_exact_match():
    """P&L reconciliation passes for exact match."""
    mismatch = reconcile_pnl(
        expected=10000.0,
        actual=10000.0,
        tolerance=1.0
    )
    
    assert mismatch.is_match is True
    assert mismatch.difference == 0.0


def test_pnl_match_within_tolerance():
    """P&L reconciliation passes within tolerance."""
    mismatch = reconcile_pnl(
        expected=10000.00,
        actual=10000.50,
        tolerance=1.0
    )
    
    assert mismatch.is_match is True
    assert abs(mismatch.difference) == 0.50


def test_pnl_mismatch_outside_tolerance():
    """P&L reconciliation fails outside tolerance."""
    mismatch = reconcile_pnl(
        expected=10000.0,
        actual=9500.0,
        tolerance=1.0
    )
    
    assert mismatch.is_match is False
    assert mismatch.difference == -500.0


def test_floating_point_tolerance():
    """Tolerance handles floating point comparison correctly."""
    mismatch = reconcile_pnl(
        expected=10000.00,
        actual=9999.99,
        tolerance=0.05
    )
    
    assert mismatch.is_match is False  # Outside tolerance
    
    mismatch2 = reconcile_pnl(
        expected=10000.00,
        actual=9999.99,
        tolerance=0.02
    )
    
    assert mismatch2.is_match is True  # Within tolerance


def test_format_report():
    """Reconciliation report formats correctly."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50),
        "BANKNIFTY": Position("BANKNIFTY", quantity=-25)
    }
    
    broker = {
        "NIFTY": 25,
        "BANKNIFTY": -25
    }
    
    result = create_reconciliation_report(
        internal,
        broker,
        expected_pnl=10000.0,
        actual_pnl=9950.0,
        pnl_tolerance=100.0
    )
    
    report = format_reconciliation_report(result)
    
    assert "POSITION RECONCILIATION REPORT" in report
    assert "NIFTY" in report
    assert "BANKNIFTY" in report
    assert "P&L RECONCILIATION" in report
    assert "10,000.00" in report
    assert "9,950.00" in report


def test_create_complete_report():
    """create_reconciliation_report combines position and P&L."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50)
    }
    
    broker = {
        "NIFTY": 50
    }
    
    result = create_reconciliation_report(
        internal,
        broker,
        expected_pnl=5000.0,
        actual_pnl=5001.0,
        pnl_tolerance=2.0
    )
    
    assert result.matched is True
    assert result.pnl_mismatch is not None
    assert result.pnl_mismatch.is_match is True
    assert not result.has_pnl_mismatch()


def test_report_with_pnl_mismatch():
    """Report correctly shows P&L mismatch."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=50)
    }
    
    broker = {
        "NIFTY": 50
    }
    
    result = create_reconciliation_report(
        internal,
        broker,
        expected_pnl=10000.0,
        actual_pnl=8000.0,
        pnl_tolerance=100.0
    )
    
    assert result.matched is False  # Overall mismatch
    assert not result.has_position_mismatches()  # Positions match
    assert result.has_pnl_mismatch()  # But P&L doesn't


def test_zero_positions():
    """Reconciliation handles zero positions."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=0)
    }
    
    broker = {
        "NIFTY": 0
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is True
    assert not result.has_position_mismatches()


def test_negative_positions():
    """Reconciliation handles negative (short) positions."""
    internal = {
        "NIFTY": Position("NIFTY", quantity=-100)
    }
    
    broker = {
        "NIFTY": -100
    }
    
    result = reconcile_positions(internal, broker)
    
    assert result.matched is True


def test_empty_reconciliation():
    """Reconciliation handles empty inputs."""
    result = reconcile_positions({}, {})
    
    assert result.matched is True
    assert len(result.position_mismatches) == 0
