import math
from datetime import datetime, UTC, timedelta
from src.core.bar import Bar
from src.indicators.atr import atr
from src.indicators.math_utils import true_range, bars_to_dataframe


def _make_bar(day: int, o: float, h: float, l: float, c: float, v: int = 1000) -> Bar:
    return Bar(
        instrument="NIFTY",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=day),
        open=o, high=h, low=l, close=c, volume=v,
    )


def test_true_range_uses_high_low_when_no_gap():
    bars = [
        _make_bar(0, o=100, h=105, l=98, c=108),   # prev close = 108
        _make_bar(1, o=108, h=110, l=100, c=105),  # bar 2 from your worked example
    ]
    df = bars_to_dataframe(bars)
    tr = true_range(df)
    assert tr.iloc[1] == 10.0   # matches your hand calculation


def test_true_range_uses_gap_when_larger_than_range():
    bars = [
        _make_bar(0, o=100, h=102, l=98, c=100),   # prev close = 100
        _make_bar(1, o=120, h=122, l=119, c=121),  # big gap up overnight
    ]
    df = bars_to_dataframe(bars)
    tr = true_range(df)
    # range_hl = 122-119=3; range_hc=|122-100|=22; range_lc=|119-100|=19
    assert tr.iloc[1] == 22.0


def test_atr_first_period_minus_one_values_are_nan():
    bars = [_make_bar(i, 100, 105, 95, 100) for i in range(5)]
    result = atr(bars, period=5)
    assert all(math.isnan(v) for v in result.iloc[:4])


def test_atr_is_average_of_true_range_over_window():
    # Construct bars with a known, constant true range of 10 each, so
    # a 3-period ATR should simply equal 10 once the window fills.
    bars = [
        _make_bar(0, o=100, h=105, l=95, c=100),   # TR = high-low = 10 (no prior close)
        _make_bar(1, o=100, h=105, l=95, c=100),   # prev close 100, TR = 10
        _make_bar(2, o=100, h=105, l=95, c=100),
        _make_bar(3, o=100, h=105, l=95, c=100),
    ]
    result = atr(bars, period=3)
    assert result.iloc[2] == 10.0
    assert result.iloc[3] == 10.0