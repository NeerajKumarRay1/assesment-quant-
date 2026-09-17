import pandas as pd
from src.core.bar import Bar
from src.indicators.math_utils import bars_to_dataframe, true_range


def atr(bars: list[Bar], period: int = 14) -> pd.Series:
    """Average True Range: rolling mean of True Range over `period` bars.
    Returns a pandas Series aligned to the input bars' order (index 0..n-1).
    First `period-1` values will be NaN - not enough history yet to average.
    """
    df = bars_to_dataframe(bars)
    tr = true_range(df)
    return tr.rolling(window=period, min_periods=period).mean()