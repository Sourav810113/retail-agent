from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..core.db import UnitOfWork
from ..domain.audit_details import OrderLookupDetails
from ..domain.enums import ActionType, Outcome
from ..domain.errors import NotFoundError
from ..domain.models import MAX_ORDER_ID_LENGTH, Order
from ..repositories.order_repository import OrderRepository
from ..repositories.return_repository import ReturnRepository
from .audit_service import AuditService

ORDER_NOT_FOUND_MESSAGE = "Order not found"


@dataclass(frozen=True)
class OrderLookupResult:
    order: Order
    returned_quantities: dict[str, int]
    return_eligible_until: date | None

    def quantity_returned(self, sku: str) -> int:
        return self.returned_quantities.get(sku, 0)


class OrderService:
    def __init__(
        self,
        uow: UnitOfWork,
        audit: AuditService,
        orders: OrderRepository | None = None,
        returns: ReturnRepository | None = None,
    ) -> None:
        self._uow = uow
        self._audit = audit
        self._orders = orders or OrderRepository(uow)
        self._returns = returns or ReturnRepository(uow)

    def lookup(self, order_id: str, email: str) -> OrderLookupResult:
        """Entry point for FR-1/FR-2: one transaction, audited, then raise.

        An unknown Order and a wrong email are indistinguishable to the caller.
        """
        result: OrderLookupResult | None = None
        with self._uow.transaction():
            order = (
                self._orders.get_with_lines(order_id)
                if len(order_id) <= MAX_ORDER_ID_LENGTH
                else None
            )
            if order is not None and order.email_matches(email):
                result = OrderLookupResult(
                    order=order,
                    returned_quantities=self._returns.returned_quantities(order_id),
                    return_eligible_until=order.return_eligible_until(),
                )
            self._audit.record(
                ActionType.ORDER_LOOKUP,
                Outcome.FOUND if result is not None else Outcome.NOT_FOUND,
                OrderLookupDetails(),
                order_id=order_id[:MAX_ORDER_ID_LENGTH],
            )
        if result is None:
            raise NotFoundError(ORDER_NOT_FOUND_MESSAGE)
        return result
