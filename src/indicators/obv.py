"""On-Balance Volume - Volume Indicator"""

import pandas as pd
from src.core.bar import Bar
from src.indicators.math_utils import bars_to_dataframe


def obv(bars: list[Bar]) -> pd.Series:
    """On-Balance Volume: volume-based momentum indicator.
    
    OBV shows whether volume is flowing into or out of an asset.
    Rising OBV suggests buying pressure; falling OBV suggests selling pressure.
    
    Logic:
        - If close > previous close: OBV += volume (buying pressure)
        - If close < previous close: OBV -= volume (selling pressure)
        - If close == previous close: OBV unchanged
    
    Args:
        bars: List of OHLCV bars
        
    Returns:
        Pandas Series of OBV values, aligned to input bars.
        First value is 0 (no previous bar to compare).
        
    Usage:
        obv_values = obv(bars)
        # Bullish: price rising + OBV rising (volume confirms trend)
        # Bearish: price falling + OBV falling
        # Divergence: price up but OBV down (weak trend, possible reversal)
    """
    df = bars_to_dataframe(bars)
    
    # Determine direction: +1 if close up, -1 if close down, 0 if unchanged
    price_change = df['close'].diff()
    direction = pd.Series(0, index=df.index)
    direction[price_change > 0] = 1
    direction[price_change < 0] = -1
    
    # OBV = cumulative sum of (volume × direction)
    obv_values = (df['volume'] * direction).cumsum()
    
    return obv_values
