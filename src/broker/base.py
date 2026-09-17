from abc import ABC, abstractmethod
from src.core.order import Order, Fill


class Broker(ABC):
    """Abstraction every broker adapter (mock or real) must satisfy.

    Strategy, Risk, and OrderManager code depend ONLY on this interface,
    never on a concrete broker. This is the dependency-inversion seam that
    lets us swap MockBroker for a future ZerodhaBroker without touching
    any trading logic.
    """

    @abstractmethod
    def submit_order(self, order: Order) -> Fill:
        """Submit an order and return the resulting Fill.

        Happy path only for now - failure modes (rejects, timeouts,
        disconnects) are added in the next pass via exceptions.
        """
        raise NotImplementedError