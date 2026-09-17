"""Tests for grid trading strategy."""

import pytest
from src.strategy import GridStrategy, GridState
from src.core.position import Position


def test_grid_strategy_enters_long_on_oversold_rsi():
    """RSI < 30 when flat → should enter long."""
    strategy = GridStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_price=100.0,
        current_position=pos,
        atr=10.0,
        rsi=25.0  # oversold
    )
    
    assert target == 1  # long 1 unit


def test_grid_strategy_enters_short_on_overbought_rsi():
    """RSI > 70 when flat → should enter short."""
    strategy = GridStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_price=100.0,
        current_position=pos,
        atr=10.0,
        rsi=75.0  # overbought
    )
    
    assert target == -1  # short 1 unit


def test_grid_strategy_stays_flat_when_rsi_neutral():
    """RSI between 30-70 when flat → should stay flat."""
    strategy = GridStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    target = strategy.calculate_target_quantity(
        instrument="NIFTY",
        current_price=100.0,
        current_position=pos,
        atr=10.0,
        rsi=50.0  # neutral
    )
    
    assert target == 0


def test_grid_spacing_calculation():
    """Grid spacing = ATR × multiplier."""
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=1.5,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter long at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    pos.quantity = 1  # simulate fill
    
    # Grid spacing = 10 × 1.5 = 15
    # Should NOT pyramid at 114 (less than 15 points)
    target = strategy.calculate_target_quantity("NIFTY", 114.0, pos, atr=10.0)
    assert target == 1  # hold
    
    # SHOULD pyramid at 115 (exactly 15 points)
    target = strategy.calculate_target_quantity("NIFTY", 115.0, pos, atr=10.0)
    assert target == 2  # added 1 more


def test_grid_adds_pyramid_level_on_favorable_move():
    """Long position + price rises by grid spacing → add pyramid."""
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=2.0,
        max_pyramid_levels=3,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter long at 100
    target = strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    assert target == 1
    pos.quantity = 1  # simulate position opened
    
    # Price moves to 120 (grid spacing = 10 × 2.0 = 20)
    target = strategy.calculate_target_quantity("NIFTY", 120.0, pos, atr=10.0)
    assert target == 2  # pyramided


def test_grid_respects_max_pyramid_levels():
    """Should not add more than max_pyramid_levels."""
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=1.0,
        max_pyramid_levels=2,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    pos.quantity = 1
    
    # First pyramid at 110
    target = strategy.calculate_target_quantity("NIFTY", 110.0, pos, atr=10.0)
    assert target == 2
    pos.quantity = 2
    
    # Should NOT add at 120 (already at max 2 levels)
    target = strategy.calculate_target_quantity("NIFTY", 120.0, pos, atr=10.0)
    assert target == 2  # hold, no more pyramids


def test_grid_triggers_stop_loss_on_adverse_move():
    """Long position + price drops by stop distance → exit."""
    strategy = GridStrategy(
        stop_loss_atr_multiplier=2.0,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter long at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    pos.quantity = 1
    
    # Stop loss = 10 × 2.0 = 20
    # Price drops to 79 (21 points down, below stop)
    target = strategy.calculate_target_quantity("NIFTY", 79.0, pos, atr=10.0)
    assert target == 0  # flattened


def test_grid_holds_position_within_stop_and_pyramid_range():
    """Price hasn't moved enough for pyramid or stop → hold position."""
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=2.0,
        stop_loss_atr_multiplier=3.0,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    pos.quantity = 1
    
    # Grid spacing = 20, stop = 30
    # At 110: not far enough for pyramid (need 120), not at stop (need 70)
    target = strategy.calculate_target_quantity("NIFTY", 110.0, pos, atr=10.0)
    assert target == 1  # hold


def test_short_grid_pyramids_downward():
    """Short position + price falls → add pyramid."""
    strategy = GridStrategy(
        grid_spacing_atr_multiplier=1.0,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter short at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=75.0)
    pos.quantity = -1
    
    # Price falls to 90 (grid spacing = 10)
    target = strategy.calculate_target_quantity("NIFTY", 90.0, pos, atr=10.0)
    assert target == -2  # added to short


def test_short_grid_stops_on_adverse_move():
    """Short position + price rises by stop distance → exit."""
    strategy = GridStrategy(
        stop_loss_atr_multiplier=2.0,
        position_size=1
    )
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter short at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=75.0)
    pos.quantity = -1
    
    # Stop loss = 20, price rises to 121
    target = strategy.calculate_target_quantity("NIFTY", 121.0, pos, atr=10.0)
    assert target == 0  # stopped out


def test_grid_clears_state_after_exit():
    """After stop loss, grid state should be cleared."""
    strategy = GridStrategy(stop_loss_atr_multiplier=2.0, position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter long
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    assert "NIFTY" in strategy._grid_states
    
    pos.quantity = 1
    # Stop out
    strategy.calculate_target_quantity("NIFTY", 79.0, pos, atr=10.0)
    
    # State should be cleared
    assert "NIFTY" not in strategy._grid_states


def test_grid_allows_reentry_after_exit():
    """After exiting, should be able to enter again."""
    strategy = GridStrategy(position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter long at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    pos.quantity = 1
    
    # Stop out
    target = strategy.calculate_target_quantity("NIFTY", 75.0, pos, atr=10.0)
    assert target == 0
    pos.quantity = 0
    
    # Should be able to enter again
    target = strategy.calculate_target_quantity("NIFTY", 80.0, pos, atr=10.0, rsi=25.0)
    assert target == 1


def test_grid_strategy_validates_parameters():
    """Constructor should reject invalid parameters."""
    with pytest.raises(ValueError):
        GridStrategy(grid_spacing_atr_multiplier=0)
    
    with pytest.raises(ValueError):
        GridStrategy(max_pyramid_levels=0)
    
    with pytest.raises(ValueError):
        GridStrategy(stop_loss_atr_multiplier=-1)
    
    with pytest.raises(ValueError):
        GridStrategy(position_size=0)


def test_grid_rejects_instrument_mismatch():
    """Should reject if instrument doesn't match position."""
    strategy = GridStrategy()
    pos = Position(instrument="NIFTY", quantity=0)
    
    with pytest.raises(ValueError, match="Instrument mismatch"):
        strategy.calculate_target_quantity(
            instrument="BANKNIFTY",
            current_position=pos,
            current_price=100.0,
            atr=10.0
        )


def test_grid_can_work_without_rsi_when_position_exists():
    """When already in position, RSI is not needed for pyramid/stop logic."""
    strategy = GridStrategy(grid_spacing_atr_multiplier=1.0, position_size=1)
    pos = Position(instrument="NIFTY", quantity=0)
    
    # Enter with RSI
    strategy.calculate_target_quantity("NIFTY", 100.0, pos, atr=10.0, rsi=25.0)
    pos.quantity = 1
    
    # Pyramid without providing RSI
    target = strategy.calculate_target_quantity("NIFTY", 110.0, pos, atr=10.0, rsi=None)
    assert target == 2  # still works


def test_grid_reset_clears_all_state():
    """reset() should clear all tracked grid states."""
    strategy = GridStrategy(position_size=1)
    pos1 = Position(instrument="NIFTY", quantity=0)
    pos2 = Position(instrument="BANKNIFTY", quantity=0)
    
    # Enter positions in multiple instruments
    strategy.calculate_target_quantity("NIFTY", 100.0, pos1, atr=10.0, rsi=25.0)
    strategy.calculate_target_quantity("BANKNIFTY", 200.0, pos2, atr=20.0, rsi=25.0)
    
    assert len(strategy._grid_states) == 2
    
    strategy.reset()
    assert len(strategy._grid_states) == 0


def test_grid_recovers_from_restart_with_existing_position():
    """If strategy restarts with existing position, should create state and respect stops."""
    strategy = GridStrategy(stop_loss_atr_multiplier=2.0, position_size=1)
    
    # Simulate: we restart and discover we already have a position
    pos = Position(instrument="NIFTY", quantity=2, avg_price=100.0)
    
    # Should create state on first call
    target = strategy.calculate_target_quantity("NIFTY", 105.0, pos, atr=10.0)
    
    # State should be created
    assert "NIFTY" in strategy._grid_states
    assert strategy._grid_states["NIFTY"].entry_price == 100.0
    
    # Should still respect stop loss
    target = strategy.calculate_target_quantity("NIFTY", 79.0, pos, atr=10.0)
    assert target == 0  # stopped out


def test_grid_state_is_tracked_per_instrument():
    """Different instruments should have independent grid states."""
    strategy = GridStrategy(position_size=1, grid_spacing_atr_multiplier=1.0)
    pos_nifty = Position(instrument="NIFTY", quantity=0)
    pos_bank = Position(instrument="BANKNIFTY", quantity=0)
    
    # Enter NIFTY long at 100
    strategy.calculate_target_quantity("NIFTY", 100.0, pos_nifty, atr=10.0, rsi=25.0)
    pos_nifty.quantity = 1
    
    # Enter BANKNIFTY short at 200
    strategy.calculate_target_quantity("BANKNIFTY", 200.0, pos_bank, atr=20.0, rsi=75.0)
    pos_bank.quantity = -1
    
    # Pyramid NIFTY
    target_nifty = strategy.calculate_target_quantity("NIFTY", 110.0, pos_nifty, atr=10.0)
    assert target_nifty == 2
    
    # Pyramid BANKNIFTY
    target_bank = strategy.calculate_target_quantity("BANKNIFTY", 180.0, pos_bank, atr=20.0)
    assert target_bank == -2
    
    # Both should have independent states
    assert len(strategy._grid_states) == 2
