"""Tests for trade blotter."""

import tempfile
from pathlib import Path
from datetime import datetime, UTC
from src.core.order import Fill, Side
from src.observability.blotter import TradeBlotter


def test_record_fill():
    """Blotter records fill correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        fill = Fill(
            order_id="order123",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill123"
        )
        
        recorded = blotter.record_fill(
            fill,
            strategy="Grid",
            costs=20.0,
            realized_pnl=150.0
        )
        
        assert recorded is True
        assert blotter.get_trade_count() == 1


def test_blotter_idempotency():
    """Duplicate fill_id is ignored (idempotent)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        fill = Fill(
            order_id="order123",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill123"
        )
        
        # First record
        recorded1 = blotter.record_fill(fill, strategy="Grid")
        assert recorded1 is True
        
        # Duplicate - should be ignored
        recorded2 = blotter.record_fill(fill, strategy="Grid")
        assert recorded2 is False
        
        # Still only one trade
        assert blotter.get_trade_count() == 1


def test_flush_and_read_trades():
    """Blotter flushes to CSV and reads correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        fill1 = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill1"
        )
        
        fill2 = Fill(
            order_id="order2",
            instrument="BANKNIFTY",
            side=Side.SELL,
            quantity=25,
            price=52000.0,
            fill_id="fill2"
        )
        
        blotter.record_fill(fill1, strategy="Grid", costs=20.0, realized_pnl=100.0)
        blotter.record_fill(fill2, strategy="SAR", costs=20.0, realized_pnl=-50.0)
        blotter.flush()
        
        # Read back
        trades = blotter.read_trades()
        assert len(trades) == 2
        
        assert trades[0].instrument == "NIFTY"
        assert trades[0].side == "BUY"
        assert trades[0].quantity == 50
        assert trades[0].price == 25000.0
        assert trades[0].strategy == "Grid"
        assert trades[0].costs == 20.0
        assert trades[0].realized_pnl == 100.0
        
        assert trades[1].instrument == "BANKNIFTY"
        assert trades[1].side == "SELL"


def test_csv_persistence():
    """CSV file persists between blotter instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        
        # First instance - write trades
        blotter1 = TradeBlotter(blotter_file)
        fill1 = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill1"
        )
        blotter1.record_fill(fill1, strategy="Grid")
        blotter1.flush()
        
        # Second instance - should load existing trades
        blotter2 = TradeBlotter(blotter_file)
        assert blotter2.get_trade_count() == 1
        
        # Add another trade
        fill2 = Fill(
            order_id="order2",
            instrument="BANKNIFTY",
            side=Side.SELL,
            quantity=25,
            price=52000.0,
            fill_id="fill2"
        )
        blotter2.record_fill(fill2, strategy="Grid")
        blotter2.flush()
        
        # Third instance - should have both
        blotter3 = TradeBlotter(blotter_file)
        trades = blotter3.read_trades()
        assert len(trades) == 2


def test_idempotency_across_instances():
    """Idempotency works across blotter instances."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        
        fill = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill1"
        )
        
        # First instance - record fill
        blotter1 = TradeBlotter(blotter_file)
        recorded1 = blotter1.record_fill(fill, strategy="Grid")
        blotter1.flush()
        assert recorded1 is True
        
        # Second instance - try to record same fill
        blotter2 = TradeBlotter(blotter_file)
        recorded2 = blotter2.record_fill(fill, strategy="Grid")
        assert recorded2 is False
        
        # Still only one trade
        trades = blotter2.read_trades()
        assert len(trades) == 1


def test_get_trades_for_symbol():
    """Can filter trades by symbol."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        # Add NIFTY trades
        for i in range(3):
            fill = Fill(
                order_id=f"order{i}",
                instrument="NIFTY",
                side=Side.BUY,
                quantity=50,
                price=25000.0 + i,
                fill_id=f"fill_nifty_{i}"
            )
            blotter.record_fill(fill, strategy="Grid")
        
        # Add BANKNIFTY trade
        fill = Fill(
            order_id="order_bn",
            instrument="BANKNIFTY",
            side=Side.SELL,
            quantity=25,
            price=52000.0,
            fill_id="fill_bn"
        )
        blotter.record_fill(fill, strategy="SAR")
        blotter.flush()
        
        # Filter by symbol
        nifty_trades = blotter.get_trades_for_symbol("NIFTY")
        assert len(nifty_trades) == 3
        assert all(t.instrument == "NIFTY" for t in nifty_trades)
        
        banknifty_trades = blotter.get_trades_for_symbol("BANKNIFTY")
        assert len(banknifty_trades) == 1


def test_multiple_fills():
    """Blotter handles multiple fills correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        # Record 10 fills
        for i in range(10):
            fill = Fill(
                order_id=f"order{i}",
                instrument="NIFTY",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                quantity=50,
                price=25000.0 + i * 10,
                fill_id=f"fill{i}"
            )
            blotter.record_fill(
                fill,
                strategy="Grid",
                costs=20.0,
                realized_pnl=float(i * 10)
            )
        
        blotter.flush()
        
        trades = blotter.read_trades()
        assert len(trades) == 10
        assert blotter.get_trade_count() == 10


def test_empty_blotter():
    """Empty blotter returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        trades = blotter.read_trades()
        assert trades == []
        assert blotter.get_trade_count() == 0


def test_correct_pnl_and_cost_fields():
    """Blotter correctly stores P&L and cost data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "test_blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        fill = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.SELL,
            quantity=50,
            price=25500.0,
            fill_id="fill1"
        )
        
        blotter.record_fill(
            fill,
            strategy="Grid",
            costs=23.45,
            realized_pnl=1250.75
        )
        blotter.flush()
        
        trades = blotter.read_trades()
        assert len(trades) == 1
        assert trades[0].costs == 23.45
        assert trades[0].realized_pnl == 1250.75
