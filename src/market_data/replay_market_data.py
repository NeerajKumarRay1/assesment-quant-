"""Replay market data from CSV files for deterministic testing and backtesting.

Provides a historical/replay feed that loads tick data from CSV files rather
than connecting to a live broker API. Useful for:
- Deterministic testing without network dependencies
- Backtesting with realistic tick-level data
- Simulating market conditions offline
"""

import csv
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from src.market_data.base import MarketData
from src.core.bar import Bar
from src.core.tick import Tick


class ReplayMarketData(MarketData):
    """Market data feed that replays ticks from a CSV file.
    
    CSV format expected:
        timestamp,symbol,price,volume
        2026-01-15T09:15:01,NIFTY,25000.00,100
        2026-01-15T09:15:02,NIFTY,25001.25,120
    
    Timestamps must be ISO 8601 format and sorted in ascending order.
    """

    def __init__(self, csv_path: str | Path) -> None:
        """Initialize replay feed from a CSV file.
        
        Args:
            csv_path: Path to CSV file containing tick data
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV is malformed or missing required columns
        """
        self._csv_path = Path(csv_path)
        if not self._csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Load and validate ticks on initialization
        self._ticks = self._load_ticks()
        
        # Index ticks by instrument for fast filtering
        self._ticks_by_instrument: dict[str, list[Tick]] = {}
        for tick in self._ticks:
            if tick.instrument not in self._ticks_by_instrument:
                self._ticks_by_instrument[tick.instrument] = []
            self._ticks_by_instrument[tick.instrument].append(tick)

    def _load_ticks(self) -> list[Tick]:
        """Load all ticks from CSV file with validation.
        
        Returns:
            List of Tick objects sorted by timestamp
            
        Raises:
            ValueError: If CSV is malformed or validation fails
        """
        ticks: list[Tick] = []
        
        with open(self._csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            # Validate required columns
            required_cols = {'timestamp', 'symbol', 'price', 'volume'}
            if reader.fieldnames is None or not required_cols.issubset(reader.fieldnames):
                raise ValueError(
                    f"CSV must contain columns: {required_cols}. "
                    f"Found: {reader.fieldnames}"
                )
            
            prev_timestamp: datetime | None = None
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    timestamp = datetime.fromisoformat(row['timestamp'])
                    symbol = row['symbol'].strip()
                    price = float(row['price'])
                    volume = int(row['volume'])
                    
                    # Validate timestamp ordering
                    if prev_timestamp is not None and timestamp < prev_timestamp:
                        raise ValueError(
                            f"Timestamps must be sorted. Row {row_num}: "
                            f"{timestamp} < {prev_timestamp}"
                        )
                    prev_timestamp = timestamp
                    
                    # Validate values
                    if price <= 0:
                        raise ValueError(f"Price must be positive. Row {row_num}: {price}")
                    if volume < 0:
                        raise ValueError(f"Volume cannot be negative. Row {row_num}: {volume}")
                    if not symbol:
                        raise ValueError(f"Symbol cannot be empty. Row {row_num}")
                    
                    ticks.append(Tick(
                        instrument=symbol,
                        timestamp=timestamp,
                        price=price,
                        volume=volume
                    ))
                    
                except (KeyError, ValueError) as e:
                    raise ValueError(f"Error parsing CSV row {row_num}: {e}") from e
        
        if not ticks:
            raise ValueError("CSV file contains no valid ticks")
        
        return ticks

    def get_bars(self, instrument: str) -> list[Bar]:
        """Return empty list - replay feed is tick-based, not bar-based.
        
        For bar data, use MockMarketData or a separate bar replay feed.
        """
        return []

    def stream_ticks(self, instrument: str) -> Iterator[Tick]:
        """Stream ticks for the given instrument in timestamp order.
        
        Args:
            instrument: Symbol to filter ticks for
            
        Yields:
            Tick objects in chronological order
        """
        for tick in self._ticks_by_instrument.get(instrument, []):
            yield tick

    def stream_all_ticks(self) -> Iterator[Tick]:
        """Stream all ticks across all instruments in timestamp order.
        
        Useful for multi-instrument strategies or market simulators.
        
        Yields:
            Tick objects in chronological order across all symbols
        """
        for tick in self._ticks:
            yield tick

    def get_instruments(self) -> set[str]:
        """Return set of all instruments present in the replay data.
        
        Returns:
            Set of instrument symbols
        """
        return set(self._ticks_by_instrument.keys())
