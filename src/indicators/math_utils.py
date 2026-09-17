import pandas as pd
from src.core.bar import Bar


def bars_to_dataframe(bars: list[Bar]) -> pd.DataFrame:
    """Convert domain Bar objects into a DataFrame for vectorized math.
    This is the ONE conversion point - indicators work in pandas internally,
    but the rest of the system never needs to import pandas."""
    return pd.DataFrame([
        {
            "timestamp": b.timestamp,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ])


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range per bar: max of (high-low, |high-prev_close|, |low-prev_close|).
    Shared primitive - reused by ATR now, and by any future volatility-aware
    indicator, so the math is defined exactly once."""
    prev_close = df["close"].shift(1)
    range_hl = df["high"] - df["low"]
    range_hc = (df["high"] - prev_close).abs()
    range_lc = (df["low"] - prev_close).abs()
    return pd.concat([range_hl, range_hc, range_lc], axis=1).max(axis=1)