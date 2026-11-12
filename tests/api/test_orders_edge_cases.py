"""US-101 edge cases for GET /orders/{order_id} (AC-1..AC-5).

Order IDs are opaque strings, so malformed IDs (non-numeric, negative, unprefixed)
must be indistinguishable from an unknown Order: the uniform AC-3 404, never a 422
that would reveal the ID format. Every such attempt is still audited (AC-5).
"""

import json
import re

import pytest

from tests.conftest import audit_rows

EMAIL_HEADER = "X-Customer-Email"
NOT_FOUND_BODY = {"error": {"code": "NOT_FOUND", "message": "Order not found"}}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")

EDGE_IDS = [
    pytest.param("abc", id="non-numeric"),
    pytest.param("ORD-ABCD", id="non-numeric-suffix"),
    pytest.param("-1", id="negative"),
    pytest.param("ORD--1001", id="negative-suffix"),
    pytest.param("0", id="zero"),
    pytest.param("1001", id="numeric-without-prefix"),
    pytest.param("ORD-1001.5", id="fractional"),
]


def lookup(client, order_id, email="asha@example.com"):
    headers = {} if email is None else {EMAIL_HEADER: email}
    return client.get(f"/orders/{order_id}", headers=headers)


@pytest.mark.parametrize("order_id", EDGE_IDS)
def test_malformed_id_returns_uniform_404(client, order_id):
    resp = lookup(client, order_id)
    assert resp.status_code == 404
    assert resp.json() == NOT_FOUND_BODY
    assert resp.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("order_id", EDGE_IDS)
def test_malformed_id_404_is_byte_identical_to_unknown_id_404(client, order_id):
    assert lookup(client, order_id).content == lookup(client, "ORD-9999").content


@pytest.mark.parametrize("order_id", EDGE_IDS)
def test_malformed_id_writes_not_found_audit_event(client, app, order_id):
    lookup(client, order_id)
    [row] = audit_rows(app.state.uow)
    assert row["action"] == "ORDER_LOOKUP"
    assert row["outcome"] == "not_found"
    assert row["order_id"] == order_id  # stored verbatim, as supplied
    assert TS_RE.match(row["occurred_at"])
    assert json.loads(row["details_json"]) == {}


@pytest.mark.parametrize(
    ("order_id", "email"),
    [
        pytest.param("ORD-9999", "asha@example.com", id="unknown-id"),
        pytest.param("ORD-1001", "ben@example.com", id="wrong-email"),
        pytest.param("ORD-1001", "asha@example.org", id="near-miss-email"),
        pytest.param("ORD-1002", "asha@example.com", id="other-customers-order"),
    ],
)
def test_404_writes_exactly_one_audit_event_without_email(client, app, order_id, email):
    resp = lookup(client, order_id, email)
    assert resp.status_code == 404
    rows = audit_rows(app.state.uow)
    assert len(rows) == 1
    row = rows[0]
    assert (row["action"], row["outcome"], row["order_id"]) == ("ORDER_LOOKUP", "not_found", order_id)
    serialized = json.dumps(row).lower()
    assert email.lower() not in serialized
    assert "@" not in serialized


def test_404_audit_is_committed_despite_error_response(client, app):
    """The NotFoundError is raised after commit, so a later lookup sees seq 1 persisted."""
    lookup(client, "ORD-9999")
    lookup(client, "ORD-1001")
    assert [(r["seq"], r["outcome"]) for r in audit_rows(app.state.uow)] == [
        (1, "not_found"),
        (2, "found"),
    ]


# AC-1: email normalization variants all resolve the Order
@pytest.mark.parametrize(
    "email",
    ["asha@example.com", "ASHA@EXAMPLE.COM", "  asha@example.com", "asha@example.com\t", "AsHa@ExAmPlE.cOm "],
)
def test_email_is_matched_case_and_whitespace_insensitively(client, email):
    resp = lookup(client, "ORD-1001", email)
    assert resp.status_code == 200
    assert "asha" not in resp.text.lower()


# AC-1: response structure
def test_line_shape_and_money_format(client):
    body = lookup(client, "ORD-1001").json()
    assert set(body) >= {"order_id", "status", "order_date", "delivery_date", "lines", "return_eligible_until"}
    for line in body["lines"]:
        assert set(line) == {"sku", "name", "quantity", "unit_price", "quantity_returned"}
        assert isinstance(line["unit_price"], str)
        assert re.fullmatch(r"\d+\.\d{2}", line["unit_price"])
        assert line["quantity_returned"] == 0


# AC-2: a delivered Order outside the window still reports its deadline
def test_old_delivered_order_still_reports_deadline(client):
    body = lookup(client, "ORD-1002", "ben@example.com").json()
    assert body["status"] == "delivered"
    assert body["delivery_date"] is not None
    assert body["return_eligible_until"] is not None


# AC-4: header must be present by name; a malformed ID does not change the 422
@pytest.mark.parametrize("order_id", ["ORD-1001", "abc", "-1"])
def test_missing_header_is_422_regardless_of_id(client, app, order_id):
    resp = lookup(client, order_id, None)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"
    assert audit_rows(app.state.uow) == []


def test_misnamed_email_header_is_422(client):
    resp = client.get("/orders/ORD-1001", headers={"X-Email": "asha@example.com"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def test_422_message_does_not_echo_header_value(client):
    resp = lookup(client, "ORD-1001", "   ")
    assert resp.status_code == 422
    assert set(resp.json()) == {"error"}
    assert set(resp.json()["error"]) == {"code", "message"}


# Review fix: order_id length cap (MAX_ORDER_ID_LENGTH = 64)
@pytest.mark.parametrize("length", [65, 10_000])
def test_over_long_id_is_uniform_404_audited_truncated(client, app, length):
    order_id = "x" * length
    resp = lookup(client, order_id)
    assert resp.status_code == 404
    assert resp.content == lookup(client, "ORD-9999").content
    first = audit_rows(app.state.uow)[0]
    assert (first["outcome"], first["order_id"]) == ("not_found", "x" * 64)


def test_id_at_length_limit_is_audited_verbatim(client, app):
    order_id = "x" * 64
    assert lookup(client, order_id).status_code == 404
    [row] = audit_rows(app.state.uow)
    assert row["order_id"] == order_id


def test_over_long_id_with_real_prefix_does_not_match(client):
    assert lookup(client, "ORD-1001" + "x" * 60).status_code == 404
