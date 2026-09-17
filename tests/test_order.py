from src.core.order import Order, Side
import pytest
import dataclasses

def test_client_order_id_is_unique_per_instance():
    order1 = Order(instrument="NIFTY", side=Side.BUY, quantity=50)
    order2 = Order(instrument="NIFTY", side=Side.BUY, quantity=50)
    assert order1.client_order_id != order2.client_order_id

def test_order_is_immutable():
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=50)
    with pytest.raises(dataclasses.FrozenInstanceError):
        order.quantity = 100