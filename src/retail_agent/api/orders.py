from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from ..domain.money import format_money
from ..services.order_service import OrderLookupResult, OrderService
from .deps import get_order_service
from .errors import ERROR_RESPONSES
from .schemas import LineView, OrderView

router = APIRouter(tags=["orders"])


def to_order_view(result: OrderLookupResult) -> OrderView:
    order = result.order
    return OrderView(
        order_id=order.order_id,
        status=order.status,
        order_date=order.order_date,
        delivery_date=order.delivery_date,
        return_eligible_until=result.return_eligible_until,
        lines=[
            LineView(
                sku=line.sku,
                name=line.name,
                quantity=line.quantity,
                unit_price=format_money(line.unit_price),
                quantity_returned=result.quantity_returned(line.sku),
            )
            for line in order.lines
        ],
        returns=[],  # Returns arrive in US-102.
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderView,
    responses=ERROR_RESPONSES,
    summary="Look up an Order by Order ID and email",
)
def get_order(
    order_id: str,
    x_customer_email: Annotated[
        str,
        Header(
            pattern=r"\S",
            description="Email on the Order; compared case-insensitively. Never echoed.",
        ),
    ],
    service: Annotated[OrderService, Depends(get_order_service)],
) -> OrderView:
    return to_order_view(service.lookup(order_id, x_customer_email))
