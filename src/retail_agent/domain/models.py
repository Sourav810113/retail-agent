"""Domain entities (AD-10: the single owner of entity definitions)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .enums import ActionType, OrderStatus, Outcome

RETURN_WINDOW_DAYS = 30
# Longer IDs cannot exist; they get the uniform 404 and are audited truncated.
MAX_ORDER_ID_LENGTH = 64


def normalize_email(email: str) -> str:
    """Canonical form for comparing Customer emails (AD-7)."""
    return email.strip().lower()


class _Entity(BaseModel):
    model_config = ConfigDict(frozen=True)


class Product(_Entity):
    sku: str
    name: str
    returnable: bool
    quantity_on_hand: int


class LineItem(_Entity):
    sku: str
    name: str
    quantity: int
    unit_price: Decimal


class Order(_Entity):
    order_id: str
    customer_email: str
    status: OrderStatus
    order_date: date
    delivery_date: date | None
    lines: tuple[LineItem, ...]

    def email_matches(self, email: str) -> bool:
        return self.customer_email == normalize_email(email)

    def return_eligible_until(self) -> date | None:
        """Last day of the Return Window (inclusive), or None if not delivered."""
        if self.status is not OrderStatus.DELIVERED or self.delivery_date is None:
            return None
        return self.delivery_date + timedelta(days=RETURN_WINDOW_DAYS)


class AuditEvent(_Entity):
    event_id: str
    occurred_at: datetime
    action: ActionType
    outcome: Outcome
    order_id: str | None = None
    return_id: str | None = None
    details_json: str
