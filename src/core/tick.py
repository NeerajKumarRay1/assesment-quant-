from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Tick:
    """One live price update for an instrument."""
    instrument: str
    timestamp: datetime
    price: float
    volume: int = 0