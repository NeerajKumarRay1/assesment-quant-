import pytest
from src.broker.mock_broker import MockBroker, BrokerRejected, BrokerTimeout, BrokerDisconnected
from src.broker.base import Broker
from src.core.order import Order, Side


def test_submit_order_returns_fill_matching_order():
    broker = MockBroker(fill_price=250.0)
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=10)

    fill = broker.submit_order(order)

    assert fill.order_id == order.client_order_id
    assert fill.instrument == order.instrument
    assert fill.side == order.side
    assert fill.quantity == order.quantity
    assert fill.price == 250.0


def test_broker_records_fill_history():
    broker = MockBroker()
    order1 = Order(instrument="NIFTY", side=Side.BUY, quantity=10)
    order2 = Order(instrument="NIFTY", side=Side.SELL, quantity=5)

    broker.submit_order(order1)
    broker.submit_order(order2)

    assert len(broker.fills) == 2
    assert broker.fills[0].order_id == order1.client_order_id
    assert broker.fills[1].order_id == order2.client_order_id


def test_broker_is_abstract():
    with pytest.raises(TypeError):
        Broker()   # cannot instantiate the abstract interface directly


def test_broker_raises_on_forced_reject():
    broker = MockBroker(force_outcome="reject")
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=10)
    with pytest.raises(BrokerRejected):
        broker.submit_order(order)


def test_broker_raises_on_forced_timeout():
    broker = MockBroker(force_outcome="timeout")
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=10)
    with pytest.raises(BrokerTimeout):
        broker.submit_order(order)


def test_broker_raises_on_forced_disconnect():
    broker = MockBroker(force_outcome="disconnect")
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=10)
    with pytest.raises(BrokerDisconnected):
        broker.submit_order(order)


def test_duplicate_submission_returns_original_fill_not_a_new_one():
    broker = MockBroker(fill_price=100.0)
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=10)

    first_fill = broker.submit_order(order)
    second_fill = broker.submit_order(order)   # same client_order_id, simulating a retry

    assert first_fill.fill_id == second_fill.fill_id
    assert len(broker.fills) == 1