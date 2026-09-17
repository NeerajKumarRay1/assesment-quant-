"""Structured JSON logging for trading events."""

import json
import logging
from pathlib import Path
from typing import Any
from src.observability.events import TradingEvent


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs log records as JSON."""
    
    # Sensitive field names that should never be logged
    SENSITIVE_FIELDS = {
        'password', 'token', 'api_key', 'secret', 'credential',
        'authorization', 'access_token', 'refresh_token'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON line.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation
        """
        log_data = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'message': record.getMessage(),
        }
        
        # Add extra fields from record
        if hasattr(record, 'event_type'):
            log_data['event_type'] = record.event_type
        
        if hasattr(record, 'instrument'):
            log_data['instrument'] = record.instrument
        
        if hasattr(record, 'order_id'):
            log_data['order_id'] = record.order_id
        
        if hasattr(record, 'metadata'):
            # Filter out sensitive fields from metadata
            filtered_metadata = self._filter_sensitive(record.metadata)
            log_data['metadata'] = filtered_metadata
        
        return json.dumps(log_data)
    
    def _filter_sensitive(self, data: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from data.
        
        Args:
            data: Dictionary that may contain sensitive fields
            
        Returns:
            Dictionary with sensitive fields removed
        """
        return {
            k: v for k, v in data.items()
            if k.lower() not in self.SENSITIVE_FIELDS
        }


class StructuredLogger:
    """Structured logger that outputs JSON lines.
    
    Usage:
        logger = StructuredLogger("trading_engine")
        logger.log_event(trading_event)
        logger.log_info("Engine started")
    """
    
    def __init__(
        self,
        name: str,
        log_file: str | Path | None = None,
        level: int = logging.INFO
    ):
        """Initialize structured logger.
        
        Args:
            name: Logger name
            log_file: Path to log file (default: logs/trading.log)
            level: Logging level (default: INFO)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Determine log file path
        if log_file is None:
            log_file = Path("logs") / "trading.log"
        else:
            log_file = Path(log_file)
        
        # Create logs directory if needed
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create file handler with JSON formatter
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def log_event(self, event: TradingEvent) -> None:
        """Log a trading event.
        
        Args:
            event: TradingEvent to log
        """
        extra = {
            'event_type': event.event_type.value,
            'instrument': event.instrument,
            'order_id': event.order_id,
            'metadata': event.metadata
        }
        
        # Choose log level based on event type
        level = self._get_log_level(event.event_type.value)
        self.logger.log(level, event.message, extra=extra)
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log info level message.
        
        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        self.logger.info(message, extra={'metadata': kwargs})
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning level message.
        
        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        self.logger.warning(message, extra={'metadata': kwargs})
    
    def log_error(self, message: str, **kwargs) -> None:
        """Log error level message.
        
        Args:
            message: Log message
            **kwargs: Additional fields to include
        """
        self.logger.error(message, extra={'metadata': kwargs})
    
    def _get_log_level(self, event_type: str) -> int:
        """Determine appropriate log level for event type.
        
        Args:
            event_type: Event type string
            
        Returns:
            Logging level constant
        """
        # Errors
        if event_type in ('ENGINE_ERROR', 'RECONCILIATION_MISMATCH'):
            return logging.ERROR
        
        # Warnings
        if event_type in (
            'RISK_REJECTED',
            'CIRCUIT_BREAKER_TRIGGERED',
            'ORDER_REJECTED',
            'ROLLOVER_REQUIRED'
        ):
            return logging.WARNING
        
        # Everything else is INFO
        return logging.INFO
