"""Seed data (AD-10: the single owner of seed rows; later stories only add).

All dates are offsets from T = ``clock.today()`` at ``create_app`` time:

| Order    | Email            | Status    | Order date | Delivery date | Purpose                        |
|----------|------------------|-----------|------------|---------------|--------------------------------|
| ORD-1001 | asha@example.com | delivered | T - 15     | T - 12        | inside the Return Window       |
| ORD-1002 | ben@example.com  | delivered | T - 50     | T - 45        | outside the Return Window      |
| ORD-1003 | chen@example.com | shipped   | T - 3      | null          | not yet delivered              |
| ORD-1004 | dana@example.com | cancelled | T - 20     | null          | cancelled                      |

Products: SKU-JACKET, SKU-SOCKS, SKU-BOOTS (returnable) and SKU-GIFTCARD
(``returnable = false``). ORD-1001 has SKU-SOCKS with quantity 2.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from ..core.clock import Clock
from ..core.db import UnitOfWork
from ..domain.money import decimal_to_cents

# (sku, name, returnable, quantity_on_hand)
PRODUCTS: tuple[tuple[str, str, bool, int], ...] = (
    ("SKU-JACKET", "Rain Jacket", True, 10),
    ("SKU-SOCKS", "Wool Socks", True, 50),
    ("SKU-BOOTS", "Hiking Boots", True, 5),
    ("SKU-GIFTCARD", "Gift Card", False, 100),
)

# (order_id, email, status, order_date offset, delivery_date offset or None)
ORDERS: tuple[tuple[str, str, str, int, int | None], ...] = (
    ("ORD-1001", "asha@example.com", "delivered", 15, 12),
    ("ORD-1002", "ben@example.com", "delivered", 50, 45),
    ("ORD-1003", "chen@example.com", "shipped", 3, None),
    ("ORD-1004", "dana@example.com", "cancelled", 20, None),
)

# (order_id, sku, quantity, unit_price)
ORDER_LINES: tuple[tuple[str, str, int, Decimal], ...] = (
    ("ORD-1001", "SKU-JACKET", 1, Decimal("89.99")),
    ("ORD-1001", "SKU-SOCKS", 2, Decimal("12.50")),
    ("ORD-1001", "SKU-GIFTCARD", 1, Decimal("25.00")),
    ("ORD-1002", "SKU-BOOTS", 1, Decimal("129.00")),
    ("ORD-1003", "SKU-SOCKS", 3, Decimal("12.50")),
    ("ORD-1004", "SKU-JACKET", 1, Decimal("89.99")),
)


def seed(uow: UnitOfWork, clock: Clock) -> None:
    """Insert the fixtures. Must run inside ``uow.transaction()``."""
    conn = uow.connection
    today = clock.today()

    def days_ago(offset: int | None) -> str | None:
        return None if offset is None else (today - timedelta(days=offset)).isoformat()

    conn.executemany(
        "INSERT INTO products (sku, name, returnable, quantity_on_hand) VALUES (?, ?, ?, ?)",
        [(sku, name, int(returnable), qty) for sku, name, returnable, qty in PRODUCTS],
    )
    conn.executemany(
        "INSERT INTO orders (order_id, customer_email, status, order_date, delivery_date)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (order_id, email, status, days_ago(ordered), days_ago(delivered))
            for order_id, email, status, ordered, delivered in ORDERS
        ],
    )
    conn.executemany(
        "INSERT INTO order_lines (order_id, sku, quantity, unit_price_cents) VALUES (?, ?, ?, ?)",
        [(o, sku, qty, decimal_to_cents(price)) for o, sku, qty, price in ORDER_LINES],
    )
