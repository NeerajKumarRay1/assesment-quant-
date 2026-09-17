from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, UTC
import uuid


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Order:
    instrument: str
    side: Side
    quantity: int
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Fill:
    order_id: str           # references Order.client_order_id
    instrument: str
    side: Side
    quantity: int
    price: float
    fill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filled_at: datetime = field(default_factory=lambda: datetime.now(UTC))