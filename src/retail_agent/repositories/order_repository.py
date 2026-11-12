from __future__ import annotations

from datetime import date

from ..core.db import UnitOfWork
from ..domain.enums import OrderStatus
from ..domain.models import LineItem, Order
from ..domain.money import cents_to_decimal


class OrderRepository:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def get_with_lines(self, order_id: str) -> Order | None:
        conn = self._uow.connection
        row = conn.execute(
            "SELECT order_id, customer_email, status, order_date, delivery_date"
            " FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if row is None:
            return None
        line_rows = conn.execute(
            "SELECT ol.sku, p.name, ol.quantity, ol.unit_price_cents"
            " FROM order_lines ol JOIN products p ON p.sku = ol.sku"
            " WHERE ol.order_id = ? ORDER BY ol.sku",
            (order_id,),
        ).fetchall()
        return Order(
            order_id=row["order_id"],
            customer_email=row["customer_email"],
            status=OrderStatus(row["status"]),
            order_date=date.fromisoformat(row["order_date"]),
            delivery_date=(
                date.fromisoformat(row["delivery_date"]) if row["delivery_date"] else None
            ),
            lines=tuple(
                LineItem(
                    sku=r["sku"],
                    name=r["name"],
                    quantity=r["quantity"],
                    unit_price=cents_to_decimal(r["unit_price_cents"]),
                )
                for r in line_rows
            ),
        )
