from abc import ABC, abstractmethod
from collections.abc import Iterator
from src.core.bar import Bar
from src.core.tick import Tick


class MarketData(ABC):
    """Abstraction every market-data source (mock or real) must satisfy.

    Two responsibilities kept deliberately separate:
    - get_bars(): historical data, used by the backtest engine
    - stream_ticks(): live data, used by the live execution loop

    Strategy/indicator code depends only on Bar/Tick objects, never on
    how they were sourced - this is what lets backtest and live share code.
    """

    @abstractmethod
    def get_bars(self, instrument: str) -> list[Bar]:
        """Return historical bars for backtesting. No lookahead: caller
        must only use bars up to the current index when making decisions."""
        raise NotImplementedError

    @abstractmethod
    def stream_ticks(self, instrument: str) -> Iterator[Tick]:
        """Yield ticks one at a time, simulating a live feed."""
        raise NotImplementedError