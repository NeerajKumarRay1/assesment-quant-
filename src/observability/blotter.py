"""Trade blotter - canonical record of executed trades."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from src.core.order import Fill


@dataclass
class BlotterRecord:
    """Single trade record in the blotter."""
    timestamp: str
    fill_id: str
    order_id: str
    instrument: str
    side: str
    quantity: int
    price: float
    strategy: str
    costs: float
    realized_pnl: float


class TradeBlotter:
    """CSV-backed trade blotter with idempotency.
    
    Maintains canonical record of all executed trades.
    Uses fill_id as idempotency key to prevent duplicates.
    
    Usage:
        blotter = TradeBlotter("data/trade_blotter.csv")
        blotter.record_fill(fill, strategy="Grid", costs=20.0, realized_pnl=150.0)
        blotter.flush()
        trades = blotter.read_trades()
    """
    
    def __init__(self, filepath: str | Path = "data/trade_blotter.csv"):
        """Initialize trade blotter.
        
        Args:
            filepath: Path to CSV file
        """
        self.filepath = Path(filepath)
        self._recorded_fill_ids: set[str] = set()
        self._pending_records: list[BlotterRecord] = []
        
        # Create directory if needed
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing fill IDs for idempotency check
        if self.filepath.exists():
            self._load_existing_fill_ids()
    
    def _load_existing_fill_ids(self) -> None:
        """Load fill IDs from existing CSV file."""
        try:
            with open(self.filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._recorded_fill_ids.add(row['fill_id'])
        except (FileNotFoundError, KeyError):
            # File doesn't exist or is malformed - start fresh
            pass
    
    def record_fill(
        self,
        fill: Fill,
        strategy: str = "Unknown",
        costs: float = 0.0,
        realized_pnl: float = 0.0
    ) -> bool:
        """Record a fill to the blotter.
        
        Idempotent - duplicate fill_id is ignored.
        
        Args:
            fill: Fill object to record
            strategy: Strategy name that generated the trade
            costs: Transaction costs for this trade
            realized_pnl: Realized P&L from this trade (if position reduced)
            
        Returns:
            True if recorded, False if duplicate
        """
        # Idempotency check
        if fill.fill_id in self._recorded_fill_ids:
            return False
        
        # Create record
        record = BlotterRecord(
            timestamp=fill.filled_at.isoformat(),
            fill_id=fill.fill_id,
            order_id=fill.order_id,
            instrument=fill.instrument,
            side=fill.side.value,
            quantity=fill.quantity,
            price=fill.price,
            strategy=strategy,
            costs=costs,
            realized_pnl=realized_pnl
        )
        
        self._pending_records.append(record)
        self._recorded_fill_ids.add(fill.fill_id)
        
        return True
    
    def flush(self) -> None:
        """Write pending records to CSV file.
        
        Appends to existing file or creates new one with headers.
        """
        if not self._pending_records:
            return
        
        # Check if file exists to determine if we need headers
        file_exists = self.filepath.exists()
        
        with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
            fieldnames = [
                'timestamp', 'fill_id', 'order_id', 'instrument',
                'side', 'quantity', 'price', 'strategy', 'costs', 'realized_pnl'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Write header if new file
            if not file_exists:
                writer.writeheader()
            
            # Write all pending records
            for record in self._pending_records:
                writer.writerow({
                    'timestamp': record.timestamp,
                    'fill_id': record.fill_id,
                    'order_id': record.order_id,
                    'instrument': record.instrument,
                    'side': record.side,
                    'quantity': record.quantity,
                    'price': record.price,
                    'strategy': record.strategy,
                    'costs': record.costs,
                    'realized_pnl': record.realized_pnl
                })
        
        # Clear pending records
        self._pending_records.clear()
    
    def read_trades(self) -> list[BlotterRecord]:
        """Read all trades from CSV file.
        
        Returns:
            List of BlotterRecord objects
        """
        if not self.filepath.exists():
            return []
        
        records = []
        with open(self.filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = BlotterRecord(
                    timestamp=row['timestamp'],
                    fill_id=row['fill_id'],
                    order_id=row['order_id'],
                    instrument=row['instrument'],
                    side=row['side'],
                    quantity=int(row['quantity']),
                    price=float(row['price']),
                    strategy=row['strategy'],
                    costs=float(row['costs']),
                    realized_pnl=float(row['realized_pnl'])
                )
                records.append(record)
        
        return records
    
    def get_trade_count(self) -> int:
        """Get total number of recorded trades.
        
        Returns:
            Number of trades in blotter
        """
        return len(self._recorded_fill_ids)
    
    def get_trades_for_symbol(self, symbol: str) -> list[BlotterRecord]:
        """Get all trades for a specific symbol.
        
        Args:
            symbol: Instrument symbol
            
        Returns:
            List of BlotterRecord objects for the symbol
        """
        all_trades = self.read_trades()
        return [t for t in all_trades if t.instrument == symbol]
    
    def clear(self) -> None:
        """Clear all blotter data (for testing).
        
        Removes CSV file and resets internal state.
        """
        if self.filepath.exists():
            self.filepath.unlink()
        self._recorded_fill_ids.clear()
        self._pending_records.clear()
