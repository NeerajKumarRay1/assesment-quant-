"""Integration tests for observability layer."""

import tempfile
from pathlib import Path
from datetime import datetime, UTC
from src.core.order import Fill, Side
from src.core.position import Position
from src.observability import (
    StructuredLogger,
    TradeBlotter,
    CollectingAlertSink,
    reconcile_positions,
    create_order_filled_event,
    create_circuit_breaker_event,
    create_reconciliation_mismatch_event,
)


def test_order_filled_to_logger_and_blotter():
    """Order fill flows to logger and blotter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        blotter_file = Path(tmpdir) / "blotter.csv"
        
        logger = StructuredLogger("test", log_file=log_file)
        blotter = TradeBlotter(blotter_file)
        
        # Create fill
        fill = Fill(
            order_id="order123",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill123"
        )
        
        # Log event
        event = create_order_filled_event(
            order_id=fill.order_id,
            instrument=fill.instrument,
            side=fill.side.value,
            quantity=fill.quantity,
            price=fill.price
        )
        logger.log_event(event)
        
        # Record to blotter
        blotter.record_fill(fill, strategy="Grid", costs=20.0, realized_pnl=100.0)
        blotter.flush()
        
        # Verify both
        assert log_file.exists()
        assert blotter_file.exists()
        
        trades = blotter.read_trades()
        assert len(trades) == 1
        assert trades[0].fill_id == "fill123"


def test_position_change_logged():
    """Position changes generate events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        position = Position("NIFTY", quantity=0)
        
        # Apply fill
        fill = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0
        )
        
        old_qty = position.quantity
        position.apply_fill(fill)
        new_qty = position.quantity
        
        # Log position change (application layer would do this)
        from src.observability.events import create_position_changed_event
        event = create_position_changed_event(
            instrument="NIFTY",
            old_quantity=old_qty,
            new_quantity=new_qty,
            realized_pnl=position.realized_pnl
        )
        logger.log_event(event)
        
        # Verify logged
        assert log_file.exists()


def test_risk_rejection_logged():
    """Risk rejections are logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        from src.observability.events import create_risk_rejected_event
        event = create_risk_rejected_event(
            instrument="NIFTY",
            desired_quantity=100,
            reason="Position cap exceeded"
        )
        logger.log_event(event)
        
        assert log_file.exists()


def test_circuit_breaker_alert():
    """Circuit breaker triggers alert."""
    alert_sink = CollectingAlertSink()
    
    # Circuit breaker activated
    event = create_circuit_breaker_event("Extreme volatility detected")
    
    # Alert on circuit breaker
    alert_sink.send(f"Circuit breaker triggered: {event.message}")
    
    alerts = alert_sink.get_alerts()
    assert len(alerts) == 1
    assert "Circuit breaker" in alerts[0]
    assert "Extreme volatility" in alerts[0]


def test_reconciliation_mismatch_alert():
    """Reconciliation mismatch triggers alert."""
    alert_sink = CollectingAlertSink()
    
    internal = {
        "NIFTY": Position("NIFTY", quantity=50)
    }
    
    broker = {
        "NIFTY": 25  # Mismatch!
    }
    
    result = reconcile_positions(internal, broker)
    
    if result.has_position_mismatches():
        for mismatch in result.position_mismatches:
            if not mismatch.is_match:
                alert_sink.send(
                    f"Position mismatch: {mismatch.symbol} "
                    f"expected {mismatch.expected_quantity}, "
                    f"got {mismatch.actual_quantity}"
                )
    
    alerts = alert_sink.get_alerts()
    assert len(alerts) == 1
    assert "Position mismatch" in alerts[0]
    assert "NIFTY" in alerts[0]


def test_no_alert_on_matching_reconciliation():
    """No alert when reconciliation matches."""
    alert_sink = CollectingAlertSink()
    
    internal = {
        "NIFTY": Position("NIFTY", quantity=50)
    }
    
    broker = {
        "NIFTY": 50  # Match
    }
    
    result = reconcile_positions(internal, broker)
    
    if result.has_position_mismatches():
        alert_sink.send("Mismatch detected")
    
    # No alerts
    assert len(alert_sink) == 0


def test_multiple_fills_to_blotter():
    """Multiple fills recorded correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        # Record 3 fills
        for i in range(3):
            fill = Fill(
                order_id=f"order{i}",
                instrument="NIFTY",
                side=Side.BUY if i % 2 == 0 else Side.SELL,
                quantity=50,
                price=25000.0 + i * 100,
                fill_id=f"fill{i}"
            )
            blotter.record_fill(fill, strategy="Grid", costs=20.0)
        
        blotter.flush()
        
        trades = blotter.read_trades()
        assert len(trades) == 3


def test_blotter_idempotency_in_retry_scenario():
    """Blotter prevents duplicate records during retries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        blotter_file = Path(tmpdir) / "blotter.csv"
        blotter = TradeBlotter(blotter_file)
        
        fill = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill1"
        )
        
        # Simulate retry - same fill submitted multiple times
        blotter.record_fill(fill, strategy="Grid")
        blotter.flush()
        
        # Retry
        recorded = blotter.record_fill(fill, strategy="Grid")
        assert recorded is False
        
        # Still only one trade
        trades = blotter.read_trades()
        assert len(trades) == 1


def test_complete_order_lifecycle():
    """Complete order lifecycle with observability."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        blotter_file = Path(tmpdir) / "blotter.csv"
        
        logger = StructuredLogger("test", log_file=log_file)
        blotter = TradeBlotter(blotter_file)
        alert_sink = CollectingAlertSink()
        
        # 1. Order submitted
        from src.observability.events import create_order_submitted_event
        submit_event = create_order_submitted_event(
            client_order_id="order1",
            instrument="NIFTY",
            side="BUY",
            quantity=50
        )
        logger.log_event(submit_event)
        
        # 2. Order filled
        fill = Fill(
            order_id="order1",
            instrument="NIFTY",
            side=Side.BUY,
            quantity=50,
            price=25000.0,
            fill_id="fill1"
        )
        
        fill_event = create_order_filled_event(
            order_id=fill.order_id,
            instrument=fill.instrument,
            side=fill.side.value,
            quantity=fill.quantity,
            price=fill.price
        )
        logger.log_event(fill_event)
        
        # 3. Record to blotter
        blotter.record_fill(fill, strategy="Grid", costs=20.0)
        blotter.flush()
        
        # 4. Verify observability
        assert log_file.exists()
        assert blotter_file.exists()
        assert len(alert_sink) == 0  # No alerts for normal fills


def test_rollover_event_logged():
    """Rollover events can be logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        from src.observability.events import EventType, TradingEvent
        
        rollover_event = TradingEvent(
            timestamp=datetime.now(UTC),
            event_type=EventType.ROLLOVER_REQUIRED,
            message="NIFTY contract expiring soon",
            instrument="NIFTY",
            metadata={"expiry": "2026-09-24", "days_until": 6}
        )
        logger.log_event(rollover_event)
        
        assert log_file.exists()
