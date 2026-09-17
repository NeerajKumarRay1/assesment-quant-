from src.broker.base import Broker
from src.core.order import Order, Fill


class BrokerRejected(Exception):
    """Order was rejected by the broker (e.g. margin, invalid instrument)."""


class BrokerTimeout(Exception):
    """Broker did not respond in time - order's fate is UNKNOWN, not failed."""


class BrokerDisconnected(Exception):
    """Broker connection is down; order was never sent."""


class MockBroker(Broker):
    """Simulated broker for the assessment. No real orders, ever.

    `force_outcome` lets tests deterministically trigger each failure mode
    without needing randomness - "success" | "reject" | "timeout" | "disconnect".
    Defaults to always succeeding.
    """

    def __init__(self, fill_price: float = 100.0, force_outcome: str = "success") -> None:
        self._fill_price = fill_price
        self._force_outcome = force_outcome
        self.fills: list[Fill] = []
        self.seen_order_ids: set[str] = set()   # duplicate-submission tracking

    def submit_order(self, order: Order) -> Fill:
        if order.client_order_id in self.seen_order_ids:
            # Duplicate submission of the same client_order_id: return the
            # ORIGINAL fill instead of creating a new one. This is what
            # makes idempotent retries safe - re-submitting a known order
            # id never produces a second fill.
            existing = next(f for f in self.fills if f.order_id == order.client_order_id)
            return existing

        if self._force_outcome == "reject":
            raise BrokerRejected(f"Order {order.client_order_id} rejected")
        if self._force_outcome == "timeout":
            raise BrokerTimeout(f"Order {order.client_order_id} timed out")
        if self._force_outcome == "disconnect":
            raise BrokerDisconnected("Broker is disconnected")

        fill = Fill(
            order_id=order.client_order_id,
            instrument=order.instrument,
            side=order.side,
            quantity=order.quantity,
            price=self._fill_price,
        )
        self.fills.append(fill)
        self.seen_order_ids.add(order.client_order_id)
        return fill