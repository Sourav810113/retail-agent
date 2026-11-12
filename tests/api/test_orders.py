import asyncio
import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from src.retail_agent.api.deps import get_order_service
from src.retail_agent.api.errors import UnexpectedErrorMiddleware
from tests.conftest import audit_rows, days_ago

EMAIL_HEADER = "X-Customer-Email"
NOT_FOUND_BODY = {"error": {"code": "NOT_FOUND", "message": "Order not found"}}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def lookup(client, order_id, email):
    headers = {} if email is None else {EMAIL_HEADER: email}
    return client.get(f"/orders/{order_id}", headers=headers)


# AC-1
def test_successful_lookup(client):
    resp = lookup(client, "ORD-1001", "Asha@Example.com ")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "order_id": "ORD-1001",
        "status": "delivered",
        "order_date": days_ago(15).isoformat(),
        "delivery_date": days_ago(12).isoformat(),
        "return_eligible_until": days_ago(12 - 30).isoformat(),
        "lines": [
            {"sku": "SKU-GIFTCARD", "name": "Gift Card", "quantity": 1,
             "unit_price": "25.00", "quantity_returned": 0},
            {"sku": "SKU-JACKET", "name": "Rain Jacket", "quantity": 1,
             "unit_price": "89.99", "quantity_returned": 0},
            {"sku": "SKU-SOCKS", "name": "Wool Socks", "quantity": 2,
             "unit_price": "12.50", "quantity_returned": 0},
        ],
        "returns": [],
    }
    assert "asha" not in resp.text.lower()
    assert all("asha" not in v.lower() for v in resp.headers.values())


# AC-2
def test_shipped_order_has_null_dates(client):
    resp = lookup(client, "ORD-1003", "chen@example.com")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "shipped"
    assert body["delivery_date"] is None
    assert body["return_eligible_until"] is None


def test_cancelled_order_has_null_dates(client):
    body = lookup(client, "ORD-1004", "dana@example.com").json()
    assert (body["status"], body["return_eligible_until"]) == ("cancelled", None)


# AC-3
def test_unknown_id_and_wrong_email_are_identical_404s(client):
    unknown = lookup(client, "ORD-9999", "asha@example.com")
    wrong = lookup(client, "ORD-1001", "ben@example.com")
    assert unknown.status_code == wrong.status_code == 404
    assert unknown.json() == wrong.json() == NOT_FOUND_BODY
    assert unknown.content == wrong.content
    assert "ben@example.com" not in wrong.text


# AC-4
@pytest.mark.parametrize("email", [None, "", "   "])
def test_missing_or_blank_email_header_is_422(client, app, email):
    resp = lookup(client, "ORD-1001", email)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"
    assert "x-customer-email" in resp.json()["error"]["message"]
    assert audit_rows(app.state.uow) == []  # request-shape errors are not audited


# AC-5
@pytest.mark.parametrize(
    ("order_id", "email", "outcome"),
    [
        ("ORD-1001", "Asha@Example.com ", "found"),
        ("ORD-1003", "chen@example.com", "found"),
        ("ORD-9999", "asha@example.com", "not_found"),
        ("ORD-1001", "ben@example.com", "not_found"),
    ],
)
def test_each_lookup_writes_exactly_one_audit_event(client, app, order_id, email, outcome):
    lookup(client, order_id, email)
    [row] = audit_rows(app.state.uow)
    assert row["action"] == "ORDER_LOOKUP"
    assert row["outcome"] == outcome
    assert row["order_id"] == order_id
    assert row["return_id"] is None
    assert row["occurred_at"] == "2026-06-15T10:30:00.123456Z"
    assert TS_RE.match(row["occurred_at"])
    assert json.loads(row["details_json"]) == {}
    assert all("@" not in str(v) for v in row.values())


def test_audit_events_accumulate_in_order(client, app):
    lookup(client, "ORD-1001", "asha@example.com")
    lookup(client, "ORD-9999", "asha@example.com")
    rows = audit_rows(app.state.uow)
    assert [(r["seq"], r["outcome"]) for r in rows] == [(1, "found"), (2, "not_found")]


# AC-6b (500)
def test_unexpected_exception_is_500_without_request_data(app):
    class Exploding:
        def lookup(self, order_id, email):
            raise RuntimeError(f"boom {order_id} {email}")

    app.dependency_overrides[get_order_service] = lambda: Exploding()
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = lookup(c, "ORD-SECRET", "asha@example.com")
    assert resp.status_code == 500
    assert resp.json() == {"error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}}
    assert "SECRET" not in resp.text and "boom" not in resp.text


# AD-7 / AD-8: the 500 path must not hand the exception to the server's logger
class _Exploding:
    def lookup(self, order_id, email):
        raise RuntimeError(f"boom {order_id} {email}")


def test_unexpected_exception_is_not_reraised_to_the_server(app):
    """Before the fix, Starlette re-raised after the handler and uvicorn logged str(exc)."""
    app.dependency_overrides[get_order_service] = lambda: _Exploding()
    with TestClient(app) as c:  # raise_server_exceptions=True: a re-raise would fail here
        resp = lookup(c, "ORD-SECRET", "asha@example.com")
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"


def test_unexpected_exception_log_omits_request_data(app, caplog):
    app.dependency_overrides[get_order_service] = lambda: _Exploding()
    with caplog.at_level(logging.DEBUG), TestClient(app) as c:
        lookup(c, "ORD-SECRET", "asha@example.com")
    app_log = "\n".join(
        r.getMessage() for r in caplog.records if r.name == "src.retail_agent.api.errors"
    )
    assert "RuntimeError" in app_log
    assert "in lookup" in app_log  # stack frames are kept for diagnosis
    # Source lines appear in frames (the f-string template); runtime values must not.
    for leaked in ("asha@example.com", "ORD-SECRET"):
        assert leaked not in app_log


def test_error_after_response_started_sends_no_second_response(caplog):
    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        message = "late " + "-".join(["asha", "example.com"])  # runtime data, not source text
        raise RuntimeError(message)

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b""}

    with caplog.at_level(logging.ERROR):
        asyncio.run(UnexpectedErrorMiddleware(inner)({"type": "http"}, receive, send))
    assert [m["type"] for m in sent] == ["http.response.start"]
    assert "RuntimeError" in caplog.text and "asha" not in caplog.text
