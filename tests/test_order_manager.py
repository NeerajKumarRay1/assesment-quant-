"""Tests for order manager."""

import pytest
from src.execution import OrderManager, OrderRecord
from src.broker.mock_broker import MockBroker, BrokerTimeout, BrokerRejected, BrokerDisconnected
from src.core.order import Side, OrderStatus


def test_order_manager_submits_order_successfully():
    """Happy path - order submits and fills."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    fill = om.submit_order("NIFTY", Side.BUY, 1)
    
    assert fill.instrument == "NIFTY"
    assert fill.side == Side.BUY
    assert fill.quantity == 1
    assert fill.price == 100.0


def test_order_manager_tracks_order_state():
    """Order state should progress from PENDING → FILLED."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    fill = om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    status = om.get_order_status("test123")
    assert status == OrderStatus.FILLED
    
    record = om.get_order_record("test123")
    assert record.fill == fill
    assert record.submit_attempts == 1


def test_order_manager_idempotent_duplicate_submission():
    """Submitting same client_order_id twice returns same fill."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    # First submission
    fill1 = om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    # Duplicate submission with same ID
    fill2 = om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    # Should return same fill
    assert fill1.fill_id == fill2.fill_id
    assert len(broker.fills) == 1  # only one fill created


def test_order_manager_retries_on_timeout():
    """Timeout should trigger retry."""
    broker = MockBroker(force_outcome="timeout")
    om = OrderManager(broker, max_retry_attempts=3)
    
    with pytest.raises(BrokerTimeout, match="timed out after 3 attempts"):
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    record = om.get_order_record("test123")
    assert record.submit_attempts == 3  # tried 3 times


def test_order_manager_timeout_then_success_on_retry():
    """Timeout followed by success should work (simulated)."""
    # First create a timeout broker
    broker = MockBroker(force_outcome="timeout")
    om = OrderManager(broker, max_retry_attempts=3)
    
    # First attempt will timeout
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    except BrokerTimeout:
        pass
    
    # Now switch broker to success mode
    broker._force_outcome = "success"
    
    # Retry should succeed (idempotent)
    fill = om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    assert fill is not None
    assert om.get_order_status("test123") == OrderStatus.FILLED


def test_order_manager_handles_rejection():
    """Rejected orders should not be retried."""
    broker = MockBroker(force_outcome="reject")
    om = OrderManager(broker)
    
    with pytest.raises(BrokerRejected, match="rejected"):
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    record = om.get_order_record("test123")
    assert record.status == OrderStatus.REJECTED
    assert record.submit_attempts == 1  # no retry on rejection


def test_order_manager_rejects_duplicate_rejected_order():
    """Re-submitting rejected order ID should raise."""
    broker = MockBroker(force_outcome="reject")
    om = OrderManager(broker)
    
    # First submission - rejected
    with pytest.raises(BrokerRejected):
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    
    # Change broker to success
    broker._force_outcome = "success"
    
    # Retry same ID - should still raise (order was rejected)
    with pytest.raises(BrokerRejected, match="previously rejected"):
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")


def test_order_manager_handles_disconnect():
    """Disconnect should not retry (order never sent)."""
    broker = MockBroker(force_outcome="disconnect")
    om = OrderManager(broker)
    
    with pytest.raises(BrokerDisconnected):
        om.submit_order("NIFTY", Side.BUY, 1)


def test_order_manager_get_pending_orders():
    """Should track pending orders."""
    broker = MockBroker(force_outcome="timeout")
    om = OrderManager(broker, max_retry_attempts=1)
    
    # Submit order that will timeout
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    except BrokerTimeout:
        pass
    
    pending = om.get_pending_orders()
    assert len(pending) == 1
    assert pending[0].order.client_order_id == "test123"


def test_order_manager_get_filled_orders():
    """Should track filled orders."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    om.submit_order("NIFTY", Side.BUY, 1, client_order_id="order1")
    om.submit_order("BANKNIFTY", Side.SELL, 2, client_order_id="order2")
    
    filled = om.get_filled_orders()
    assert len(filled) == 2
    assert all(r.status == OrderStatus.FILLED for r in filled)


def test_order_manager_pending_excludes_filled_and_rejected():
    """Pending should not include filled or rejected orders."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    # Filled order
    om.submit_order("NIFTY", Side.BUY, 1, client_order_id="filled1")
    
    # Rejected order
    broker._force_outcome = "reject"
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="reject1")
    except BrokerRejected:
        pass
    
    # Timed out order
    broker._force_outcome = "timeout"
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="timeout1")
    except BrokerTimeout:
        pass
    
    pending = om.get_pending_orders()
    assert len(pending) == 1
    assert pending[0].order.client_order_id == "timeout1"


def test_order_manager_reconcile_order():
    """Reconciliation should update order state."""
    broker = MockBroker(force_outcome="timeout")
    om = OrderManager(broker, max_retry_attempts=1)
    
    # Order times out
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    except BrokerTimeout:
        pass
    
    assert om.get_order_status("test123") == OrderStatus.ACKNOWLEDGED
    
    # Simulate broker providing fill later
    from src.core.order import Fill
    broker_fill = Fill(
        order_id="test123",
        instrument="NIFTY",
        side=Side.BUY,
        quantity=1,
        price=100.0
    )
    
    om.reconcile_order("test123", broker_fill)
    
    assert om.get_order_status("test123") == OrderStatus.FILLED
    record = om.get_order_record("test123")
    assert record.fill == broker_fill


def test_order_manager_reconcile_unknown_order():
    """Reconciling unknown order should create record (restart recovery)."""
    broker = MockBroker()
    om = OrderManager(broker)
    
    from src.core.order import Fill
    broker_fill = Fill(
        order_id="unknown123",
        instrument="NIFTY",
        side=Side.BUY,
        quantity=1,
        price=100.0
    )
    
    # Reconcile order we don't know about
    om.reconcile_order("unknown123", broker_fill)
    
    # Should create record
    status = om.get_order_status("unknown123")
    assert status == OrderStatus.FILLED


def test_order_manager_mark_rejected():
    """Should be able to mark order as rejected."""
    broker = MockBroker(force_outcome="timeout")
    om = OrderManager(broker, max_retry_attempts=1)
    
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    except BrokerTimeout:
        pass
    
    # Mark as rejected during reconciliation
    om.mark_rejected("test123", "Insufficient margin")
    
    assert om.get_order_status("test123") == OrderStatus.REJECTED
    record = om.get_order_record("test123")
    assert "margin" in record.rejection_reason.lower()


def test_order_manager_tracks_multiple_instruments():
    """Should handle multiple instruments independently."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    fill1 = om.submit_order("NIFTY", Side.BUY, 1, client_order_id="nifty1")
    fill2 = om.submit_order("BANKNIFTY", Side.SELL, 2, client_order_id="bank1")
    fill3 = om.submit_order("NIFTY", Side.SELL, 1, client_order_id="nifty2")
    
    assert fill1.instrument == "NIFTY"
    assert fill2.instrument == "BANKNIFTY"
    assert fill3.instrument == "NIFTY"
    
    all_orders = om.get_all_orders()
    assert len(all_orders) == 3


def test_order_manager_auto_generates_order_id():
    """Should auto-generate client_order_id if not provided."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    fill1 = om.submit_order("NIFTY", Side.BUY, 1)  # no ID provided
    fill2 = om.submit_order("NIFTY", Side.BUY, 1)  # no ID provided
    
    # Should have different IDs
    assert fill1.order_id != fill2.order_id


def test_order_manager_record_tracks_attempts_and_time():
    """OrderRecord should track submission metadata."""
    broker = MockBroker(force_outcome="timeout")
    om = OrderManager(broker, max_retry_attempts=2)
    
    try:
        om.submit_order("NIFTY", Side.BUY, 1, client_order_id="test123")
    except BrokerTimeout:
        pass
    
    record = om.get_order_record("test123")
    assert record.submit_attempts == 2
    assert record.last_attempt_time is not None


def test_order_manager_get_order_status_raises_on_unknown():
    """Should raise KeyError for unknown order ID."""
    broker = MockBroker()
    om = OrderManager(broker)
    
    with pytest.raises(KeyError, match="not found"):
        om.get_order_status("unknown_id")


def test_order_manager_restart_recovery_scenario():
    """Simulate restart: discover existing orders and reconcile."""
    broker = MockBroker(fill_price=100.0)
    om = OrderManager(broker)
    
    # Before crash: submit order
    om.submit_order("NIFTY", Side.BUY, 1, client_order_id="pre_crash")
    
    # Simulate restart: create NEW OrderManager instance
    om_after_restart = OrderManager(broker)
    
    # OrderManager doesn't know about pre_crash order
    assert len(om_after_restart.get_all_orders()) == 0
    
    # Reconcile with broker data (broker has fill)
    from src.core.order import Fill
    broker_fill = Fill(
        order_id="pre_crash",
        instrument="NIFTY",
        side=Side.BUY,
        quantity=1,
        price=100.0
    )
    
    om_after_restart.reconcile_order("pre_crash", broker_fill)
    
    # Now OrderManager knows about it
    assert len(om_after_restart.get_all_orders()) == 1
    assert om_after_restart.get_order_status("pre_crash") == OrderStatus.FILLED
