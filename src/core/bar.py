from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    """One OHLCV candle for an instrument over a fixed time period."""
    instrument: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int