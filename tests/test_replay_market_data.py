"""Tests for replay market data feed."""

import pytest
from pathlib import Path
from datetime import datetime
from src.market_data.replay_market_data import ReplayMarketData


# Use the sample CSV file in the data directory
SAMPLE_CSV = Path("data/sample_ticks.csv")


def test_load_valid_csv():
    """Replay feed should load valid CSV successfully."""
    feed = ReplayMarketData(SAMPLE_CSV)
    assert feed is not None


def test_load_nonexistent_csv_raises_error():
    """Loading nonexistent CSV should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        ReplayMarketData("nonexistent.csv")


def test_stream_ticks_returns_correct_instrument():
    """Stream should filter ticks by instrument."""
    feed = ReplayMarketData(SAMPLE_CSV)
    nifty_ticks = list(feed.stream_ticks("NIFTY"))
    
    assert len(nifty_ticks) == 10
    assert all(t.instrument == "NIFTY" for t in nifty_ticks)


def test_stream_ticks_preserves_timestamp_order():
    """Ticks should be returned in chronological order."""
    feed = ReplayMarketData(SAMPLE_CSV)
    ticks = list(feed.stream_ticks("NIFTY"))
    
    timestamps = [t.timestamp for t in ticks]
    assert timestamps == sorted(timestamps)


def test_stream_ticks_has_correct_prices():
    """Tick prices should match CSV data."""
    feed = ReplayMarketData(SAMPLE_CSV)
    ticks = list(feed.stream_ticks("NIFTY"))
    
    # Check first and last tick prices from sample_ticks.csv
    assert ticks[0].price == 25000.00
    assert ticks[0].volume == 100
    assert ticks[-1].price == 24999.00
    assert ticks[-1].volume == 105


def test_stream_ticks_empty_for_unknown_instrument():
    """Streaming unknown instrument returns empty."""
    feed = ReplayMarketData(SAMPLE_CSV)
    ticks = list(feed.stream_ticks("UNKNOWN"))
    assert ticks == []


def test_stream_all_ticks_returns_all_instruments():
    """Stream all should return ticks from all instruments."""
    feed = ReplayMarketData(SAMPLE_CSV)
    all_ticks = list(feed.stream_all_ticks())
    
    # Sample CSV has 10 NIFTY + 5 BANKNIFTY = 15 total
    assert len(all_ticks) == 15


def test_stream_all_ticks_maintains_global_order():
    """All ticks should be in chronological order across instruments."""
    feed = ReplayMarketData(SAMPLE_CSV)
    all_ticks = list(feed.stream_all_ticks())
    
    timestamps = [t.timestamp for t in all_ticks]
    assert timestamps == sorted(timestamps)


def test_get_instruments_returns_all_symbols():
    """Should return set of all instruments in CSV."""
    feed = ReplayMarketData(SAMPLE_CSV)
    instruments = feed.get_instruments()
    
    assert instruments == {"NIFTY", "BANKNIFTY"}


def test_get_bars_returns_empty():
    """Replay feed is tick-based, not bar-based."""
    feed = ReplayMarketData(SAMPLE_CSV)
    bars = feed.get_bars("NIFTY")
    assert bars == []


def test_malformed_csv_missing_column(tmp_path):
    """CSV missing required column should raise error."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("timestamp,symbol,price\n2026-01-15T09:15:01,NIFTY,25000.00\n")
    
    with pytest.raises(ValueError, match="must contain columns"):
        ReplayMarketData(csv_file)


def test_malformed_csv_invalid_timestamp(tmp_path):
    """CSV with invalid timestamp should raise error."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "timestamp,symbol,price,volume\n"
        "not-a-timestamp,NIFTY,25000.00,100\n"
    )
    
    with pytest.raises(ValueError, match="Error parsing"):
        ReplayMarketData(csv_file)


def test_malformed_csv_invalid_price(tmp_path):
    """CSV with invalid price should raise error."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "timestamp,symbol,price,volume\n"
        "2026-01-15T09:15:01,NIFTY,not-a-number,100\n"
    )
    
    with pytest.raises(ValueError, match="Error parsing"):
        ReplayMarketData(csv_file)


def test_csv_with_negative_price(tmp_path):
    """CSV with negative price should raise error."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "timestamp,symbol,price,volume\n"
        "2026-01-15T09:15:01,NIFTY,-100.00,100\n"
    )
    
    with pytest.raises(ValueError, match="Price must be positive"):
        ReplayMarketData(csv_file)


def test_csv_with_out_of_order_timestamps(tmp_path):
    """CSV with unsorted timestamps should raise error."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "timestamp,symbol,price,volume\n"
        "2026-01-15T09:15:02,NIFTY,25000.00,100\n"
        "2026-01-15T09:15:01,NIFTY,25001.00,100\n"
    )
    
    with pytest.raises(ValueError, match="must be sorted"):
        ReplayMarketData(csv_file)


def test_empty_csv_raises_error(tmp_path):
    """CSV with only headers should raise error."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("timestamp,symbol,price,volume\n")
    
    with pytest.raises(ValueError, match="no valid ticks"):
        ReplayMarketData(csv_file)


def test_csv_with_empty_symbol(tmp_path):
    """CSV with empty symbol should raise error."""
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text(
        "timestamp,symbol,price,volume\n"
        "2026-01-15T09:15:01,,25000.00,100\n"
    )
    
    with pytest.raises(ValueError, match="Symbol cannot be empty"):
        ReplayMarketData(csv_file)
