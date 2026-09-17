import pytest
from src.core.order import Order, Fill, Side
from src.core.position import Position
from src.core.instrument import Instrument
from src.core.signal import Signal


def test_fill_id_distinct_from_order_id():
    order = Order(instrument="NIFTY", side=Side.BUY, quantity=50)
    fill = Fill(order_id=order.client_order_id, instrument="NIFTY",
                side=Side.BUY, quantity=50, price=100.0)
    assert fill.fill_id != fill.order_id


def test_position_opens_long_from_flat():
    pos = Position(instrument="NIFTY")
    fill = Fill(order_id="x", instrument="NIFTY", side=Side.BUY,
                quantity=10, price=100.0)
    pos.apply_fill(fill)
    assert pos.quantity == 10
    assert pos.avg_price == 100.0
    assert pos.realized_pnl == 0.0


def test_position_averages_up_on_adding_to_long():
    pos = Position(instrument="NIFTY")
    pos.apply_fill(Fill(order_id="x", instrument="NIFTY", side=Side.BUY,
                         quantity=10, price=100.0))
    pos.apply_fill(Fill(order_id="x", instrument="NIFTY", side=Side.BUY,
                         quantity=10, price=110.0))
    assert pos.quantity == 20
    assert pos.avg_price == 105.0


def test_position_realizes_pnl_on_partial_close():
    pos = Position(instrument="NIFTY")
    pos.apply_fill(Fill(order_id="x", instrument="NIFTY", side=Side.BUY,
                         quantity=10, price=100.0))
    pos.apply_fill(Fill(order_id="x", instrument="NIFTY", side=Side.SELL,
                         quantity=4, price=120.0))
    assert pos.quantity == 6
    assert pos.realized_pnl == 80.0   # 4 * (120 - 100)
    assert pos.avg_price == 100.0     # unchanged for the remaining long


def test_position_flips_side_through_zero():
    pos = Position(instrument="NIFTY")
    pos.apply_fill(Fill(order_id="x", instrument="NIFTY", side=Side.BUY,
                         quantity=10, price=100.0))
    pos.apply_fill(Fill(order_id="x", instrument="NIFTY", side=Side.SELL,
                         quantity=15, price=110.0))
    assert pos.quantity == -5
    assert pos.avg_price == 110.0     # new short leg priced at the flip fill
    assert pos.realized_pnl == 100.0  # 10 * (110 - 100)


def test_position_rejects_mismatched_instrument_fill():
    pos = Position(instrument="NIFTY")
    bad_fill = Fill(order_id="x", instrument="BANKNIFTY", side=Side.BUY,
                     quantity=10, price=100.0)
    with pytest.raises(ValueError):
        pos.apply_fill(bad_fill)


def test_instrument_defaults():
    inst = Instrument(symbol="NIFTY", exchange="NSE")
    assert inst.lot_size == 1
    assert inst.expiry is None


def test_signal_is_frozen():
    import dataclasses
    sig = Signal(instrument="NIFTY", side=Side.BUY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        sig.strength = 2.0