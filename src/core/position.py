from dataclasses import dataclass
from src.core.order import Fill, Side


@dataclass
class Position:
    """Mutable running position for one instrument, built by replaying Fills.

    Not frozen: unlike Order/Fill (facts), a Position is derived state that
    updates as new fills arrive. This is the ONE mutable core object -
    deliberately, because "current position" is inherently a running total.
    """
    instrument: str
    quantity: int = 0          # positive = long, negative = short
    avg_price: float = 0.0
    realized_pnl: float = 0.0

    def apply_fill(self, fill: Fill) -> None:
        if fill.instrument != self.instrument:
            raise ValueError(
                f"Fill instrument {fill.instrument} does not match "
                f"position instrument {self.instrument}"
            )

        signed_qty = fill.quantity if fill.side == Side.BUY else -fill.quantity
        new_quantity = self.quantity + signed_qty

        is_reducing = (
            self.quantity != 0
            and (self.quantity > 0) != (signed_qty > 0)
        )

        if is_reducing:
            closed_qty = min(abs(signed_qty), abs(self.quantity))
            direction = 1 if self.quantity > 0 else -1
            self.realized_pnl += direction * closed_qty * (fill.price - self.avg_price)

        if new_quantity == 0:
            self.avg_price = 0.0
        elif (self.quantity >= 0 and signed_qty > 0) or (self.quantity <= 0 and signed_qty < 0):
            # adding to position in the same direction -> weighted avg price
            total_cost = self.avg_price * abs(self.quantity) + fill.price * abs(signed_qty)
            self.avg_price = total_cost / abs(new_quantity)
        elif is_reducing and (new_quantity > 0) != (self.quantity > 0) and new_quantity != 0:
            # flipped through zero to the other side -> new avg price is fill price
            self.avg_price = fill.price

        self.quantity = new_quantity

    def unrealized_pnl(self, current_price: float) -> float:
        if self.quantity == 0:
            return 0.0
        return self.quantity * (current_price - self.avg_price)