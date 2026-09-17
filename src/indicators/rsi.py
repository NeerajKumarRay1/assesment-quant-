import pandas as pd
from src.core.bar import Bar
from src.indicators.math_utils import bars_to_dataframe


def rsi(bars: list[Bar], period: int = 14) -> pd.Series:
    """Relative Strength Index, using Wilder's smoothing (an EMA with
    alpha = 1/period). Returns values 0-100; first `period` values will
    be NaN/unstable since there isn't enough history to smooth yet.
    """
    df = bars_to_dataframe(bars)
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))