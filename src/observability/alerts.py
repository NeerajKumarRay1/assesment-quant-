"""Alert sink abstraction for notifications."""

from typing import Protocol
import logging


class AlertSink(Protocol):
    """Protocol for alert notification systems.
    
    Implementations can send alerts via:
    - Logging (LoggingAlertSink)
    - SMS (future)
    - Telegram (future)
    - Slack (future)
    - Email (future)
    """
    
    def send(self, message: str) -> None:
        """Send alert notification.
        
        Args:
            message: Alert message to send
        """
        ...


class LoggingAlertSink:
    """Alert sink that logs alerts at WARNING level.
    
    Simple implementation for assessment. Real production would use
    external notification service.
    """
    
    def __init__(self, logger_name: str = "alerts"):
        """Initialize logging alert sink.
        
        Args:
            logger_name: Name for the logger
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.WARNING)
        
        # Add console handler if none exists
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '🚨 ALERT: %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def send(self, message: str) -> None:
        """Log alert at WARNING level.
        
        Args:
            message: Alert message
        """
        self.logger.warning(message)


class CollectingAlertSink:
    """Alert sink that collects alerts in memory.
    
    Useful for testing - allows inspection of what alerts were sent.
    """
    
    def __init__(self):
        """Initialize collecting alert sink."""
        self.alerts: list[str] = []
    
    def send(self, message: str) -> None:
        """Collect alert in memory.
        
        Args:
            message: Alert message
        """
        self.alerts.append(message)
    
    def get_alerts(self) -> list[str]:
        """Get all collected alerts.
        
        Returns:
            List of alert messages
        """
        return self.alerts.copy()
    
    def clear(self) -> None:
        """Clear all collected alerts."""
        self.alerts.clear()
    
    def __len__(self) -> int:
        """Get number of alerts collected."""
        return len(self.alerts)
