from datetime import date

from src.retail_agent.main import create_app
from tests.conftest import T, days_ago, fetch_all


# AC-7
def test_seed_dates_are_offsets_from_clock_today(app):
    rows = {r["order_id"]: r for r in fetch_all(app.state.uow, "SELECT * FROM orders")}
    assert rows["ORD-1001"]["delivery_date"] == days_ago(12).isoformat()
    assert rows["ORD-1002"]["delivery_date"] == days_ago(45).isoformat()
    assert rows["ORD-1003"]["order_date"] == days_ago(3).isoformat()


def test_seed_covers_required_fixtures(app):
    uow = app.state.uow
    orders = fetch_all(uow, "SELECT * FROM orders")
    delivered_age = [
        (T - date.fromisoformat(o["delivery_date"])).days
        for o in orders
        if o["status"] == "delivered"
    ]
    assert any(age <= 30 for age in delivered_age)
    assert any(age > 30 for age in delivered_age)
    statuses = {o["status"] for o in orders}
    assert {"shipped", "cancelled"} <= statuses
    assert fetch_all(uow, "SELECT sku FROM products WHERE returnable = 0")
    assert fetch_all(uow, "SELECT * FROM order_lines WHERE quantity >= 2")


def test_seed_money_stored_as_integer_cents(app):
    [row] = fetch_all(
        app.state.uow,
        "SELECT unit_price_cents, typeof(unit_price_cents) AS t FROM order_lines"
        " WHERE order_id = 'ORD-1001' AND sku = 'SKU-JACKET'",
    )
    assert row == {"unit_price_cents": 8999, "t": "integer"}


def test_create_app_without_seed_is_empty(clock):
    app = create_app(clock=clock, seed=False)
    assert fetch_all(app.state.uow, "SELECT * FROM orders") == []


def test_apps_do_not_share_state(clock):
    a, b = create_app(clock=clock), create_app(clock=clock)
    assert a.state.db is not b.state.db


def test_docs_served(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()


def test_openapi_declares_error_response(client):
    spec = client.get("/openapi.json").json()
    ref = "#/components/schemas/ErrorResponse"
    for path in ("/orders/{order_id}", "/healthz"):
        responses = spec["paths"][path]["get"]["responses"]
        for status in ("404", "422", "503"):
            schema = responses[status]["content"]["application/json"]["schema"]
            assert schema == {"$ref": ref}, (path, status)
    assert "ErrorResponse" in spec["components"]["schemas"]
