"""Tests for EMA (Exponential Moving Average) indicator."""

import pytest
from datetime import datetime, UTC
from src.core.bar import Bar
from src.indicators.ema import ema
import pandas as pd


def create_bars_with_prices(prices: list[float]) -> list[Bar]:
    """Helper to create bars with specific close prices."""
    bars = []
    for i, price in enumerate(prices):
        # Calculate proper timestamp (handle minute overflow)
        total_minutes = 9 * 60 + 15 + i  # Start at 9:15
        hour = (total_minutes // 60) % 24
        minute = total_minutes % 60
        bar = Bar(
            instrument="TEST",
            timestamp=datetime(2024, 1, 1, hour, minute, tzinfo=UTC),
            open=price,
            high=price + 1,
            low=price - 1,
            close=price,
            volume=1000
        )
        bars.append(bar)
    return bars


def test_ema_first_values_are_nan():
    """EMA should be NaN for first (period-1) bars."""
    prices = [100] * 20
    bars = create_bars_with_prices(prices)
    
    ema_values = ema(bars, period=10)
    
    # First 9 values should be NaN
    for i in range(9):
        assert pd.isna(ema_values.iloc[i])
    
    # 10th value should not be NaN
    assert not pd.isna(ema_values.iloc[9])


def test_ema_flat_prices_equals_price():
    """EMA of constant prices should equal that price."""
    prices = [100.0] * 30
    bars = create_bars_with_prices(prices)
    
    ema_values = ema(bars, period=10)
    
    # After warmup, EMA should equal 100
    assert ema_values.iloc[-1] == pytest.approx(100.0)


def test_ema_trending_up_follows_trend():
    """EMA should follow upward trending prices."""
    prices = list(range(100, 150))  # 100, 101, 102, ..., 149
    bars = create_bars_with_prices(prices)
    
    ema_values = ema(bars, period=10)
    
    # EMA should be increasing
    valid_ema = ema_values.dropna()
    for i in range(1, len(valid_ema)):
        assert valid_ema.iloc[i] > valid_ema.iloc[i-1]


def test_ema_lags_behind_price():
    """EMA should lag behind actual prices (smoothing effect)."""
    # Sharp price jump
    prices = [100] * 20 + [120] * 20
    bars = create_bars_with_prices(prices)
    
    ema_values = ema(bars, period=10)
    
    # At the jump point (index 20), EMA should be less than 120
    # because it's smoothing
    assert ema_values.iloc[20] < 120.0
    
    # But eventually catches up
    assert ema_values.iloc[-1] > 110.0


def test_ema_shorter_period_more_responsive():
    """Shorter period EMA should be closer to current price."""
    prices = [100] * 20 + [120] * 10
    bars = create_bars_with_prices(prices)
    
    ema_short = ema(bars, period=5)
    ema_long = ema(bars, period=20)
    
    # After the jump, short EMA should be higher (closer to 120)
    assert ema_short.iloc[-1] > ema_long.iloc[-1]


def test_ema_different_periods():
    """EMA should work with various periods."""
    prices = list(range(100, 150))
    bars = create_bars_with_prices(prices)
    
    for period in [5, 10, 20, 50]:
        if len(bars) >= period:
            ema_values = ema(bars, period=period)
            # Should have (period-1) NaN values
            nan_count = ema_values.isna().sum()
            assert nan_count == period - 1
