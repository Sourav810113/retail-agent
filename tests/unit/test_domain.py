from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.retail_agent.domain import audit_details
from src.retail_agent.domain.audit_details import (
    AUDIT_CONTRACT,
    RefundCalculatedDetails,
    ReturnRequestedDetails,
)
from src.retail_agent.domain.enums import ActionType, DenialReason, OrderStatus
from src.retail_agent.domain.errors import (
    NotFoundError,
    ReturnDeniedError,
    ServiceUnavailableError,
)
from src.retail_agent.domain.models import Order, normalize_email


def _order(status: OrderStatus, delivery: date | None) -> Order:
    return Order(
        order_id="ORD-X",
        customer_email="asha@example.com",
        status=status,
        order_date=date(2026, 1, 1),
        delivery_date=delivery,
        lines=(),
    )


@pytest.mark.parametrize(
    "raw",
    ["asha@example.com", "Asha@Example.com ", "  ASHA@EXAMPLE.COM", "\tasha@example.com\n"],
)
def test_normalize_email(raw):
    assert normalize_email(raw) == "asha@example.com"


def test_email_matches_is_case_and_whitespace_insensitive():
    order = _order(OrderStatus.DELIVERED, date(2026, 1, 5))
    assert order.email_matches("Asha@Example.com ")
    assert not order.email_matches("ben@example.com")
    assert not order.email_matches("   ")


def test_return_eligible_until_is_delivery_plus_30():
    order = _order(OrderStatus.DELIVERED, date(2026, 1, 31))
    assert order.return_eligible_until() == date(2026, 3, 2)


@pytest.mark.parametrize(
    "status", [OrderStatus.PLACED, OrderStatus.SHIPPED, OrderStatus.CANCELLED]
)
def test_return_eligible_until_null_when_not_delivered(status):
    assert _order(status, None).return_eligible_until() is None


def test_no_details_model_has_an_email_field():
    for _, model in AUDIT_CONTRACT.values():
        assert not any("email" in name for name in model.model_fields)


def test_contract_covers_every_action():
    assert set(AUDIT_CONTRACT) == set(ActionType)


def test_details_forbid_extra_fields():
    with pytest.raises(ValidationError):
        audit_details.OrderLookupDetails(email="asha@example.com")


def test_refund_details_quantized_and_serialized_as_string():
    d = RefundCalculatedDetails(refund_amount=Decimal("40"))
    assert d.model_dump_json() == '{"refund_amount":"40.00"}'


def test_return_requested_details_serialize_reason():
    d = ReturnRequestedDetails(line_count=2, denial_reason=DenialReason.ITEM_NOT_RETURNABLE)
    assert d.model_dump_json() == '{"line_count":2,"denial_reason":"ITEM_NOT_RETURNABLE"}'


def test_errors_carry_safe_messages():
    assert NotFoundError("Order not found").message == "Order not found"
    assert NotFoundError().message == "Not found"
    denied = ReturnDeniedError(DenialReason.ORDER_NOT_DELIVERED)
    assert denied.reason is DenialReason.ORDER_NOT_DELIVERED
    assert denied.message == "Return request denied"
    assert ServiceUnavailableError().message == "Service unhealthy"
