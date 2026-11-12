from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.retail_agent.api.deps import get_health_service
from src.retail_agent.api.errors import validation_message
from src.retail_agent.domain.errors import ServiceUnavailableError


# AC-6
def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_healthz_503_when_check_fails(app):
    class Failing:
        def check(self):
            raise ServiceUnavailableError()

    app.dependency_overrides[get_health_service] = lambda: Failing()
    with TestClient(app) as c:
        resp = c.get("/healthz")
    assert resp.status_code == 503
    assert resp.json() == {"error": {"code": "UNHEALTHY", "message": "Service unhealthy"}}


def test_healthz_503_when_store_is_closed(app):
    app.state.db.close()
    with TestClient(app) as c:
        resp = c.get("/healthz")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "UNHEALTHY"


# AC-6b
def test_unknown_path_is_404_in_error_shape(client):
    resp = client.get("/no-such-path")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "NOT_FOUND", "message": "Not found"}}


def test_wrong_method_is_405_in_error_shape(client):
    resp = client.post("/healthz")
    assert resp.status_code == 405
    assert resp.json() == {"error": {"code": "METHOD_NOT_ALLOWED", "message": "Method not allowed"}}
    assert resp.headers["allow"] == "GET"


def test_validation_message_never_echoes_input():
    exc = RequestValidationError(
        [
            {"loc": ("body", "lines", 0, "quantity"), "type": "int_parsing",
             "msg": "Input should be a valid integer, got SECRET-VALUE", "input": "SECRET-VALUE"},
            {"loc": ("header", "x-customer-email"), "type": "missing", "msg": "Field required",
             "input": None},
        ]
    )
    msg = validation_message(exc.errors())
    assert msg == "body.lines.0.quantity: int_parsing; header.x-customer-email: missing"
    assert "SECRET" not in msg


def test_validation_message_fallback():
    assert validation_message([]) == "Invalid request"
