from collections.abc import Iterator
from src.market_data.base import MarketData
from src.core.bar import Bar
from src.core.tick import Tick


class MockMarketData(MarketData):
    """Simulated market data for the assessment. Wraps a fixed, caller-
    supplied list of bars per instrument - no network, no real feed.

    Ticks are derived by yielding each bar's close price as one tick -
    a simple, deterministic way to simulate a live feed from the same
    data used for backtesting, without needing separate tick fixtures.
    """

    def __init__(self, bars_by_instrument: dict[str, list[Bar]]) -> None:
        self._bars_by_instrument = bars_by_instrument

    def get_bars(self, instrument: str) -> list[Bar]:
        return list(self._bars_by_instrument.get(instrument, []))

    def stream_ticks(self, instrument: str) -> Iterator[Tick]:
        for bar in self._bars_by_instrument.get(instrument, []):
            yield Tick(
                instrument=bar.instrument,
                timestamp=bar.timestamp,
                price=bar.close,
                volume=bar.volume,
            )