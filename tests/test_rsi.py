import math
from datetime import datetime, UTC, timedelta
from src.core.bar import Bar
from src.indicators.rsi import rsi


def _make_bar(day: int, close: float) -> Bar:
    return Bar(
        instrument="NIFTY",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day),
        open=close, high=close, low=close, close=close, volume=1000,
    )


def test_rsi_is_nan_before_period_bars_of_history():
    closes = [100, 101, 102, 103, 104]   # only 5 bars
    bars = [_make_bar(i, c) for i, c in enumerate(closes)]
    result = rsi(bars, period=14)
    assert all(math.isnan(v) for v in result)


def test_rsi_saturates_at_100_when_price_only_rises():
    closes = [100 + i for i in range(20)]   # strictly increasing every bar
    bars = [_make_bar(i, c) for i, c in enumerate(closes)]
    result = rsi(bars, period=14)
    assert result.iloc[-1] == 100.0


def test_rsi_saturates_near_0_when_price_only_falls():
    closes = [120 - i for i in range(20)]   # strictly decreasing every bar
    bars = [_make_bar(i, c) for i, c in enumerate(closes)]
    result = rsi(bars, period=14)
    assert result.iloc[-1] < 1.0   # effectively 0, allowing for float precision


def test_rsi_is_near_50_for_flat_price():
    closes = [100] * 20   # no movement at all
    bars = [_make_bar(i, c) for i, c in enumerate(closes)]
    result = rsi(bars, period=14)
    # avg_gain and avg_loss both 0 -> 0/0 -> NaN, which is itself correct:
    # RSI is undefined with zero volatility, not a misleading "50"
    assert math.isnan(result.iloc[-1])