"""Tests for OBV (On-Balance Volume) indicator."""

from datetime import datetime, UTC
from src.core.bar import Bar
from src.indicators.obv import obv


def create_bars_with_data(price_volume_pairs: list[tuple[float, int]]) -> list[Bar]:
    """Helper to create bars with specific prices and volumes."""
    bars = []
    for i, (price, vol) in enumerate(price_volume_pairs):
        bar = Bar(
            instrument="TEST",
            timestamp=datetime(2024, 1, 1, 9, 15 + i, tzinfo=UTC),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price,
            volume=vol
        )
        bars.append(bar)
    return bars


def test_obv_first_value_is_zero():
    """OBV should start at 0 (no previous bar to compare)."""
    data = [(100, 1000), (101, 1000), (102, 1000)]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    assert obv_values.iloc[0] == 0


def test_obv_increases_on_price_up():
    """OBV should increase when price goes up."""
    data = [
        (100, 1000),  # baseline
        (101, 500),   # price up → OBV += 500
        (102, 300),   # price up → OBV += 300
    ]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    assert obv_values.iloc[0] == 0
    assert obv_values.iloc[1] == 500   # 0 + 500
    assert obv_values.iloc[2] == 800   # 500 + 300


def test_obv_decreases_on_price_down():
    """OBV should decrease when price goes down."""
    data = [
        (100, 1000),  # baseline
        (99, 500),    # price down → OBV -= 500
        (98, 300),    # price down → OBV -= 300
    ]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    assert obv_values.iloc[0] == 0
    assert obv_values.iloc[1] == -500   # 0 - 500
    assert obv_values.iloc[2] == -800   # -500 - 300


def test_obv_unchanged_on_flat_price():
    """OBV should remain unchanged when price doesn't change."""
    data = [
        (100, 1000),
        (100, 500),   # price flat → OBV unchanged
        (100, 300),   # price flat → OBV unchanged
    ]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    assert obv_values.iloc[0] == 0
    assert obv_values.iloc[1] == 0
    assert obv_values.iloc[2] == 0


def test_obv_mixed_movements():
    """OBV should handle mixed up/down movements."""
    data = [
        (100, 1000),  # baseline
        (101, 200),   # up: OBV = +200
        (102, 300),   # up: OBV = +500
        (101, 150),   # down: OBV = +350
        (103, 400),   # up: OBV = +750
    ]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    assert obv_values.iloc[0] == 0
    assert obv_values.iloc[1] == 200
    assert obv_values.iloc[2] == 500
    assert obv_values.iloc[3] == 350
    assert obv_values.iloc[4] == 750


def test_obv_volume_matters():
    """OBV magnitude should depend on volume."""
    data = [
        (100, 1000),
        (101, 10000),  # large volume move
        (102, 100),    # small volume move
    ]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    # First move should dominate
    assert obv_values.iloc[1] == 10000
    assert obv_values.iloc[2] == 10100


def test_obv_can_be_negative():
    """OBV can go negative with sustained selling."""
    data = [
        (100, 1000),
        (99, 500),
        (98, 600),
        (97, 700),
    ]
    bars = create_bars_with_data(data)
    
    obv_values = obv(bars)
    
    # All down moves
    assert obv_values.iloc[-1] == -1800  # -500 - 600 - 700
