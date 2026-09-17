from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Instrument:
    symbol: str
    exchange: str            # e.g. "NSE", "MCX"
    lot_size: int = 1
    tick_size: float = 0.05
    expiry: date | None = None   # None for equities/spot, set for derivatives