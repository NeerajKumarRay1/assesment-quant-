from dataclasses import dataclass
from src.core.order import Side


@dataclass(frozen=True)
class Signal:
    """Strategy's intent, BEFORE risk sizing. Not yet an Order."""
    instrument: str
    side: Side
    strength: float = 1.0     # optional conviction score, e.g. for sizing