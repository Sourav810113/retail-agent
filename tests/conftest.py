from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.retail_agent.core.clock import FixedClock
from src.retail_agent.core.db import UnitOfWork, connect
from src.retail_agent.main import create_app
from src.retail_agent.repositories.schema import apply_schema
from src.retail_agent.repositories.seed import seed

T_INSTANT = datetime(2026, 6, 15, 10, 30, 0, 123456, tzinfo=UTC)
T = T_INSTANT.date()


def days_ago(n: int) -> date:
    return T - timedelta(days=n)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(T_INSTANT)


@pytest.fixture
def app(clock: FixedClock) -> FastAPI:
    return create_app(clock=clock)


@pytest.fixture
def client(app: FastAPI):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def uow(clock: FixedClock) -> UnitOfWork:
    """A seeded UnitOfWork without the HTTP layer, for service tests."""
    conn = connect()
    apply_schema(conn)
    uow = UnitOfWork(conn)
    with uow.transaction():
        seed(uow, clock)
    return uow


def fetch_all(uow: UnitOfWork, sql: str, params: tuple = ()) -> list[dict]:
    with uow.transaction():
        return [dict(r) for r in uow.connection.execute(sql, params).fetchall()]


def audit_rows(uow: UnitOfWork) -> list[dict]:
    return fetch_all(uow, "SELECT * FROM audit_events ORDER BY seq")
