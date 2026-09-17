"""Exponential Moving Average - Trend Indicator"""

import pandas as pd
from src.core.bar import Bar
from src.indicators.math_utils import bars_to_dataframe


def ema(bars: list[Bar], period: int = 20) -> pd.Series:
    """Exponential Moving Average: trend-following indicator.
    
    EMA gives more weight to recent prices, making it more responsive to
    new information than a simple moving average (SMA).
    
    Formula:
        EMA_t = (Price_t × k) + (EMA_{t-1} × (1 - k))
        where k = 2 / (period + 1)
    
    Args:
        bars: List of OHLCV bars
        period: Number of periods for EMA calculation (default: 20)
        
    Returns:
        Pandas Series of EMA values, aligned to input bars.
        First (period-1) values will be NaN.
        
    Usage:
        ema_20 = ema(bars, period=20)
        # Buy when price > EMA (uptrend)
        # Sell when price < EMA (downtrend)
    """
    df = bars_to_dataframe(bars)
    # pandas ewm (exponentially weighted moving average)
    # min_periods ensures we have enough data before calculating
    return df['close'].ewm(span=period, min_periods=period, adjust=False).mean()
