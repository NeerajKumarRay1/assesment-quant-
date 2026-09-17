"""Tests for Stop-and-Reverse strategy."""

import pytest
from src.strategy import StopAndReverseStrategy, SARState
from src.core.position import Position


def test_sar_enters_long_from_flat_on_oversold():
    """Flat + RSI < 30 → go long."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=25.0
    )
    
    assert target == 1


def test_sar_enters_short_from_flat_on_overbought():
    """Flat + RSI > 70 → go short."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=75.0
    )
    
    assert target == -1


def test_sar_stays_flat_when_rsi_neutral():
    """Flat + neutral RSI → stay flat."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=50.0
    )
    
    assert target == 0


def test_sar_holds_long_when_rsi_neutral():
    """Long + neutral RSI → hold long."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=1)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=50.0
    )
    
    assert target == 1


def test_sar_holds_short_when_rsi_neutral():
    """Short + neutral RSI → hold short."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=-1)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=50.0
    )
    
    assert target == -1


def test_sar_reverses_long_to_short():
    """Long + RSI > 70 → reverse to short."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=1)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=75.0
    )
    
    assert target == -1


def test_sar_reverses_short_to_long():
    """Short + RSI < 30 → reverse to long."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=-1)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=25.0
    )
    
    assert target == 1


def test_sar_maintains_long_on_continued_oversold():
    """Long + RSI still < 30 → hold long."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=1)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=20.0
    )
    
    assert target == 1


def test_sar_maintains_short_on_continued_overbought():
    """Short + RSI still > 70 → hold short."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=-1)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=80.0
    )
    
    assert target == -1


def test_sar_uses_custom_position_size():
    """Strategy should use configured position_size."""
    strategy = StopAndReverseStrategy(position_size=5)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_position=pos,
        rsi=25.0
    )
    
    assert target == 5


def test_sar_uses_custom_rsi_thresholds():
    """Strategy should respect custom RSI thresholds."""
    strategy = StopAndReverseStrategy(
        position_size=1,
        rsi_oversold=20.0,
        rsi_overbought=80.0
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # RSI=25 is between 20 and 80, so neutral
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=25.0)
    assert target == 0
    
    # RSI=15 is below 20, so long
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=15.0)
    assert target == 1
    
    # RSI=85 is above 80, so short
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=85.0)
    assert target == -1


def test_sar_validates_position_size():
    """position_size must be positive."""
    with pytest.raises(ValueError, match="position_size"):
        StopAndReverseStrategy(position_size=0)
    
    with pytest.raises(ValueError, match="position_size"):
        StopAndReverseStrategy(position_size=-1)


def test_sar_validates_rsi_thresholds():
    """RSI thresholds must be valid."""
    # oversold >= overbought
    with pytest.raises(ValueError, match="less than"):
        StopAndReverseStrategy(rsi_oversold=70.0, rsi_overbought=30.0)
    
    # out of range
    with pytest.raises(ValueError, match="between 0 and 100"):
        StopAndReverseStrategy(rsi_oversold=-10.0)
    
    with pytest.raises(ValueError, match="between 0 and 100"):
        StopAndReverseStrategy(rsi_overbought=110.0)


def test_sar_rejects_instrument_mismatch():
    """Should reject if instrument doesn't match position."""
    strategy = StopAndReverseStrategy()
    pos = Position(instrument="NIFTY", quantity=0)
    
    with pytest.raises(ValueError, match="Instrument mismatch"):
        strategy.calculate_target_quantity(
            instrument="BANKNIFTY",
            current_position=pos,
            rsi=50.0
        )


def test_sar_state_detection():
    """get_state_from_quantity should correctly identify states."""
    strategy = StopAndReverseStrategy()
    
    assert strategy.get_state_from_quantity(0) == SARState.FLAT
    assert strategy.get_state_from_quantity(1) == SARState.LONG
    assert strategy.get_state_from_quantity(5) == SARState.LONG
    assert strategy.get_state_from_quantity(-1) == SARState.SHORT
    assert strategy.get_state_from_quantity(-5) == SARState.SHORT


def test_sar_full_cycle_flat_long_short_long():
    """Test complete cycle: FLAT → LONG → SHORT → LONG."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Start flat
    assert strategy.get_state_from_quantity(pos.quantity) == SARState.FLAT
    
    # Go long
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=25.0)
    assert target == 1
    pos.quantity = target
    assert strategy.get_state_from_quantity(pos.quantity) == SARState.LONG
    
    # Hold long
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=50.0)
    assert target == 1
    
    # Reverse to short
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=75.0)
    assert target == -1
    pos.quantity = target
    assert strategy.get_state_from_quantity(pos.quantity) == SARState.SHORT
    
    # Hold short
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=60.0)
    assert target == -1
    
    # Reverse back to long
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=25.0)
    assert target == 1
    pos.quantity = target
    assert strategy.get_state_from_quantity(pos.quantity) == SARState.LONG


def test_sar_independent_instruments():
    """Different instruments should be handled independently."""
    strategy = StopAndReverseStrategy(position_size=1)
    pos_nifty = Position(instrument="NIFTY", quantity=0)
    pos_bank = Position(instrument="BANKNIFTY", quantity=0)
    
    # NIFTY goes long
    target_nifty = strategy.calculate_target_quantity("NIFTY", pos_nifty, rsi=25.0)
    assert target_nifty == 1
    
    # BANKNIFTY goes short
    target_bank = strategy.calculate_target_quantity("BANKNIFTY", pos_bank, rsi=75.0)
    assert target_bank == -1
    
    # Both are independent
    assert target_nifty != target_bank


def test_sar_at_exact_threshold_boundaries():
    """Test behavior at exact threshold values."""
    strategy = StopAndReverseStrategy(
        position_size=1,
        rsi_oversold=30.0,
        rsi_overbought=70.0
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # At exact oversold boundary (29.99 < 30, but 30.0 is not)
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=29.99)
    assert target == 1  # should trigger long
    
    # At exactly 30.0 (boundary)
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=30.0)
    assert target == 0  # neutral zone
    
    # At exactly 70.0 (boundary)
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=70.0)
    assert target == 0  # neutral zone
    
    # Just above overbought boundary
    target = strategy.calculate_target_quantity("NIFTY", pos, rsi=70.01)
    assert target == -1  # should trigger short
