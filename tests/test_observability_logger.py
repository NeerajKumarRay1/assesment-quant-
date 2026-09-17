"""Tests for structured logging."""

import json
import tempfile
from pathlib import Path
from src.observability.events import EventType, TradingEvent, create_order_filled_event
from src.observability.logger import StructuredLogger, JSONFormatter


def test_event_to_dict():
    """Event converts to dictionary correctly."""
    from datetime import datetime, UTC
    
    event = TradingEvent(
        timestamp=datetime(2026, 9, 18, 10, 30, 0, tzinfo=UTC),
        event_type=EventType.ORDER_FILLED,
        message="Test order filled",
        instrument="NIFTY",
        order_id="test123",
        metadata={"price": 25000.0, "quantity": 50}
    )
    
    data = event.to_dict()
    
    assert data['timestamp'] == "2026-09-18T10:30:00+00:00"
    assert data['event_type'] == "ORDER_FILLED"
    assert data['message'] == "Test order filled"
    assert data['instrument'] == "NIFTY"
    assert data['order_id'] == "test123"
    assert data['metadata']['price'] == 25000.0


def test_structured_logger_logs_event():
    """StructuredLogger logs events to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        event = create_order_filled_event(
            order_id="order123",
            instrument="NIFTY",
            side="BUY",
            quantity=50,
            price=25000.0
        )
        
        logger.log_event(event)
        
        # Read and verify JSON log
        assert log_file.exists()
        with open(log_file, 'r') as f:
            line = f.readline()
            log_data = json.loads(line)
            
            assert log_data['level'] == "INFO"
            assert log_data['event_type'] == "ORDER_FILLED"
            assert log_data['instrument'] == "NIFTY"
            assert log_data['metadata']['price'] == 25000.0


def test_json_formatter_filters_sensitive_fields():
    """JSONFormatter removes sensitive fields from metadata."""
    formatter = JSONFormatter()
    
    # Test filtering
    sensitive_data = {
        'api_key': 'secret123',
        'password': 'pass456',
        'price': 25000.0,
        'quantity': 50
    }
    
    filtered = formatter._filter_sensitive(sensitive_data)
    
    assert 'api_key' not in filtered
    assert 'password' not in filtered
    assert filtered['price'] == 25000.0
    assert filtered['quantity'] == 50


def test_logger_no_credentials_leaked():
    """Verify credentials are not logged."""
    from datetime import datetime, UTC
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        event = TradingEvent(
            timestamp=datetime.now(UTC),
            event_type=EventType.ORDER_FILLED,
            message="Test",
            metadata={
                'token': 'secret_token',
                'price': 25000.0
            }
        )
        
        logger.log_event(event)
        
        # Verify token not in log
        with open(log_file, 'r') as f:
            content = f.read()
            assert 'secret_token' not in content
            assert '25000.0' in content


def test_log_levels_for_event_types():
    """Different event types use appropriate log levels."""
    from datetime import datetime, UTC
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        # INFO level event
        info_event = TradingEvent(
            timestamp=datetime.now(UTC),
            event_type=EventType.ORDER_FILLED,
            message="Order filled"
        )
        logger.log_event(info_event)
        
        # WARNING level event
        warning_event = TradingEvent(
            timestamp=datetime.now(UTC),
            event_type=EventType.RISK_REJECTED,
            message="Risk rejected"
        )
        logger.log_event(warning_event)
        
        # ERROR level event
        error_event = TradingEvent(
            timestamp=datetime.now(UTC),
            event_type=EventType.ENGINE_ERROR,
            message="Engine error"
        )
        logger.log_event(error_event)
        
        # Read log and check levels
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            info_log = json.loads(lines[0])
            assert info_log['level'] == "INFO"
            
            warning_log = json.loads(lines[1])
            assert warning_log['level'] == "WARNING"
            
            error_log = json.loads(lines[2])
            assert error_log['level'] == "ERROR"


def test_log_info_warning_error_methods():
    """Logger helper methods work correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        logger.log_info("Info message", price=25000.0)
        logger.log_warning("Warning message", reason="test")
        logger.log_error("Error message", error="failure")
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 3
            
            info = json.loads(lines[0])
            assert info['level'] == "INFO"
            assert info['message'] == "Info message"
            
            warning = json.loads(lines[1])
            assert warning['level'] == "WARNING"
            
            error = json.loads(lines[2])
            assert error['level'] == "ERROR"


def test_valid_json_output():
    """All log output is valid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        # Log various events
        for i in range(5):
            event = create_order_filled_event(
                order_id=f"order{i}",
                instrument="NIFTY",
                side="BUY",
                quantity=50,
                price=25000.0 + i
            )
            logger.log_event(event)
        
        # Verify all lines are valid JSON
        with open(log_file, 'r') as f:
            for line in f:
                data = json.loads(line)  # Will raise if invalid
                assert 'timestamp' in data
                assert 'level' in data
                assert 'message' in data
