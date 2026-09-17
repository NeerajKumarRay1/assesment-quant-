"""Observability package for trading system.

Provides structured logging, trade blotter, reconciliation, and alerting.
"""

from src.observability.events import (
    EventType,
    TradingEvent,
    create_order_submitted_event,
    create_order_filled_event,
    create_order_rejected_event,
    create_position_changed_event,
    create_risk_rejected_event,
    create_circuit_breaker_event,
    create_reconciliation_mismatch_event,
)
from src.observability.logger import StructuredLogger, JSONFormatter
from src.observability.alerts import AlertSink, LoggingAlertSink, CollectingAlertSink
from src.observability.blotter import TradeBlotter, BlotterRecord
from src.observability.reconciliation import (
    PositionMismatch,
    PnLMismatch,
    ReconciliationResult,
    reconcile_positions,
    reconcile_pnl,
    format_reconciliation_report,
    create_reconciliation_report,
)

__all__ = [
    # Events
    'EventType',
    'TradingEvent',
    'create_order_submitted_event',
    'create_order_filled_event',
    'create_order_rejected_event',
    'create_position_changed_event',
    'create_risk_rejected_event',
    'create_circuit_breaker_event',
    'create_reconciliation_mismatch_event',
    
    # Logger
    'StructuredLogger',
    'JSONFormatter',
    
    # Alerts
    'AlertSink',
    'LoggingAlertSink',
    'CollectingAlertSink',
    
    # Blotter
    'TradeBlotter',
    'BlotterRecord',
    
    # Reconciliation
    'PositionMismatch',
    'PnLMismatch',
    'ReconciliationResult',
    'reconcile_positions',
    'reconcile_pnl',
    'format_reconciliation_report',
    'create_reconciliation_report',
]
