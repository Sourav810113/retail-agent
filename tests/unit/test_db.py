import sqlite3
import threading

import pytest

from src.retail_agent.core.db import UnitOfWork, connect
from src.retail_agent.repositories.schema import apply_schema


@pytest.fixture
def bare_uow() -> UnitOfWork:
    conn = connect()
    apply_schema(conn)
    return UnitOfWork(conn)


def _insert_product(uow: UnitOfWork, sku: str = "SKU-X") -> None:
    uow.connection.execute(
        "INSERT INTO products (sku, name, returnable, quantity_on_hand) VALUES (?, 'X', 1, 1)",
        (sku,),
    )


def _count(uow: UnitOfWork) -> int:
    with uow.transaction():
        return uow.connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]


def test_connection_settings():
    conn = connect()
    assert conn.isolation_level is None
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_commit_on_success(bare_uow):
    with bare_uow.transaction():
        assert bare_uow.in_transaction
        _insert_product(bare_uow)
    assert not bare_uow.in_transaction
    assert _count(bare_uow) == 1


def test_rollback_on_exception(bare_uow):
    with pytest.raises(ValueError):
        with bare_uow.transaction():
            _insert_product(bare_uow)
            raise ValueError("boom")
    assert not bare_uow.in_transaction
    assert _count(bare_uow) == 0


def test_nested_transaction_raises_runtime_error(bare_uow):
    with bare_uow.transaction():
        with pytest.raises(RuntimeError):
            with bare_uow.transaction():
                pass  # pragma: no cover
    assert not bare_uow.in_transaction


def test_connection_outside_transaction_raises(bare_uow):
    with pytest.raises(RuntimeError):
        _ = bare_uow.connection


def test_failed_commit_rolls_back(bare_uow):
    with pytest.raises(sqlite3.IntegrityError):
        with bare_uow.transaction():
            bare_uow.connection.execute("PRAGMA defer_foreign_keys = ON")
            bare_uow.connection.execute(
                "INSERT INTO order_lines (order_id, sku, quantity, unit_price_cents)"
                " VALUES ('ORD-NOPE', 'SKU-NOPE', 1, 100)"
            )
    assert not bare_uow.in_transaction
    assert not bare_uow._conn.in_transaction  # connection is usable again
    assert _count(bare_uow) == 0


def test_other_thread_waits_instead_of_raising(bare_uow):
    entered = threading.Event()
    release = threading.Event()
    seen: list[bool] = []

    def holder():
        with bare_uow.transaction():
            entered.set()
            release.wait(timeout=5)

    def waiter():
        with bare_uow.transaction():
            seen.append(True)

    t1 = threading.Thread(target=holder)
    t1.start()
    entered.wait(timeout=5)
    t2 = threading.Thread(target=waiter)
    t2.start()
    t2.join(timeout=0.2)
    assert seen == []  # blocked on the lock, not failed
    release.set()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert seen == [True]
