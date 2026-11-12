import json
import sqlite3

import pytest

from src.retail_agent.domain.audit_details import (
    OrderLookupDetails,
    ReturnRequestedDetails,
    ReturnViewedDetails,
)
from src.retail_agent.domain.enums import ActionType, OrderStatus, Outcome
from src.retail_agent.domain.errors import NotFoundError, ServiceUnavailableError
from src.retail_agent.services.audit_service import AuditService
from src.retail_agent.services.health_service import HealthService
from src.retail_agent.services.order_service import OrderService
from tests.conftest import T_INSTANT, audit_rows, days_ago

TS_RE = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"


@pytest.fixture
def audit(uow, clock):
    return AuditService(uow, clock)


@pytest.fixture
def orders(uow, audit):
    return OrderService(uow, audit)


# --- OrderService.lookup -------------------------------------------------


def test_lookup_found(orders, uow):
    result = orders.lookup("ORD-1001", "Asha@Example.com ")
    assert result.order.order_id == "ORD-1001"
    assert result.order.status is OrderStatus.DELIVERED
    assert result.return_eligible_until == days_ago(12 - 30)
    assert result.returned_quantities == {}
    assert result.quantity_returned("SKU-SOCKS") == 0
    assert not uow.in_transaction

    [row] = audit_rows(uow)
    assert (row["action"], row["outcome"], row["order_id"]) == ("ORDER_LOOKUP", "found", "ORD-1001")


@pytest.mark.parametrize(
    ("order_id", "email"),
    [("ORD-9999", "asha@example.com"), ("ORD-1001", "ben@example.com")],
)
def test_lookup_not_found_is_audited_and_committed_before_raise(orders, uow, order_id, email):
    with pytest.raises(NotFoundError) as exc:
        orders.lookup(order_id, email)
    assert exc.value.message == "Order not found"
    assert not uow.in_transaction

    [row] = audit_rows(uow)
    assert (row["outcome"], row["order_id"]) == ("not_found", order_id)
    assert "@" not in row["details_json"]


def test_lookup_unknown_and_wrong_email_raise_identical_errors(orders):
    errors = []
    for args in [("ORD-9999", "asha@example.com"), ("ORD-1001", "nope@example.com")]:
        with pytest.raises(NotFoundError) as exc:
            orders.lookup(*args)
        errors.append((type(exc.value), exc.value.message))
    assert errors[0] == errors[1]


def test_lookup_unexpected_error_rolls_back_audit(uow, audit):
    class Boom(Exception):
        pass

    class ExplodingReturns:
        def returned_quantities(self, order_id):
            raise Boom

    service = OrderService(uow, audit, returns=ExplodingReturns())
    with pytest.raises(Boom):
        service.lookup("ORD-1001", "asha@example.com")
    assert audit_rows(uow) == []


# --- AuditService.record -------------------------------------------------


def test_record_requires_transaction(audit):
    with pytest.raises(RuntimeError):
        audit.record(ActionType.ORDER_LOOKUP, Outcome.FOUND, OrderLookupDetails())


def test_record_writes_clock_time_and_details(audit, uow):
    with uow.transaction():
        event = audit.record(
            ActionType.RETURN_REQUESTED,
            Outcome.DENIED,
            ReturnRequestedDetails(line_count=1),
            order_id="ORD-1001",
        )
    [row] = audit_rows(uow)
    assert row["event_id"] == event.event_id
    assert row["occurred_at"] == "2026-06-15T10:30:00.123456Z"
    assert event.occurred_at == T_INSTANT
    assert row["return_id"] is None
    assert json.loads(row["details_json"]) == {"line_count": 1, "denial_reason": None}


def test_record_rejects_outcome_not_valid_for_action(audit, uow):
    with uow.transaction():
        with pytest.raises(ValueError):
            audit.record(ActionType.ORDER_LOOKUP, Outcome.ACCEPTED, OrderLookupDetails())


def test_record_rejects_wrong_details_model(audit, uow):
    with uow.transaction():
        with pytest.raises(TypeError):
            audit.record(ActionType.ORDER_LOOKUP, Outcome.FOUND, ReturnViewedDetails())


def test_event_ids_are_unique(audit, uow):
    with uow.transaction():
        a = audit.record(ActionType.ORDER_LOOKUP, Outcome.FOUND, OrderLookupDetails())
        b = audit.record(ActionType.ORDER_LOOKUP, Outcome.FOUND, OrderLookupDetails())
    assert a.event_id != b.event_id
    assert [r["seq"] for r in audit_rows(uow)] == [1, 2]


# --- HealthService --------------------------------------------------------


def test_health_ok(uow):
    HealthService(uow).check()
    assert not uow.in_transaction


def test_health_fails_when_store_unreadable(uow):
    uow._conn.close()
    with pytest.raises(ServiceUnavailableError) as exc:
        HealthService(uow).check()
    assert isinstance(exc.value.__cause__, sqlite3.Error)
    assert not uow.in_transaction


def test_lookup_over_long_id_skips_repository_and_truncates_audit(uow, audit):
    class SpyRepo:
        calls = 0

        def get_with_lines(self, order_id):
            SpyRepo.calls += 1

    service = OrderService(uow, audit, orders=SpyRepo())
    with pytest.raises(NotFoundError):
        service.lookup("ORD-" + "9" * 100, "asha@example.com")
    assert SpyRepo.calls == 0
    [row] = audit_rows(uow)
    assert row["order_id"] == ("ORD-" + "9" * 100)[:64]
    assert row["outcome"] == "not_found"
