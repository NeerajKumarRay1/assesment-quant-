import pytest
from datetime import datetime, UTC
from src.market_data.base import MarketData
from src.market_data.mock_market_data import MockMarketData
from src.core.bar import Bar


def _sample_bars() -> list[Bar]:
    return [
        Bar(instrument="NIFTY", timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            open=100.0, high=105.0, low=99.0, close=103.0, volume=1000),
        Bar(instrument="NIFTY", timestamp=datetime(2026, 1, 2, tzinfo=UTC),
            open=103.0, high=108.0, low=101.0, close=107.0, volume=1500),
    ]


def test_get_bars_returns_supplied_bars():
    md = MockMarketData({"NIFTY": _sample_bars()})
    bars = md.get_bars("NIFTY")
    assert len(bars) == 2
    assert bars[0].close == 103.0
    assert bars[1].close == 107.0


def test_get_bars_returns_empty_list_for_unknown_instrument():
    md = MockMarketData({"NIFTY": _sample_bars()})
    assert md.get_bars("BANKNIFTY") == []


def test_stream_ticks_yields_one_tick_per_bar_at_close_price():
    md = MockMarketData({"NIFTY": _sample_bars()})
    ticks = list(md.stream_ticks("NIFTY"))
    assert len(ticks) == 2
    assert ticks[0].price == 103.0
    assert ticks[1].price == 107.0
    assert ticks[0].instrument == "NIFTY"


def test_market_data_is_abstract():
    with pytest.raises(TypeError):
        MarketData()