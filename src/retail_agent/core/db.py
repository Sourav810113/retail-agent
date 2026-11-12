"""SQLite connection factory and the UnitOfWork (AD-2, AD-3)."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

# Process-wide and non-re-entrant: serialises every transaction in the process.
_TRANSACTION_LOCK = threading.Lock()


def connect() -> sqlite3.Connection:
    """Open the app's single shared in-memory connection."""
    conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class UnitOfWork:
    """Owns transaction boundaries on the shared connection.

    Only entry-point service methods call :meth:`transaction`. Everything they
    call asserts :attr:`in_transaction` instead. Opening a transaction while
    the current thread already has one raises ``RuntimeError`` rather than
    deadlocking on the non-re-entrant lock. Another thread simply waits.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._local = threading.local()

    @property
    def in_transaction(self) -> bool:
        return getattr(self._local, "active", False)

    @property
    def connection(self) -> sqlite3.Connection:
        """The connection, available only inside a transaction."""
        if not self.in_transaction:
            raise RuntimeError("database access outside a transaction")
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator[UnitOfWork]:
        if self.in_transaction:
            raise RuntimeError("a transaction is already active")
        with _TRANSACTION_LOCK:
            self._conn.execute("BEGIN IMMEDIATE")
            self._local.active = True
            try:
                yield self
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                try:
                    self._conn.execute("COMMIT")
                except BaseException:
                    self._conn.execute("ROLLBACK")
                    raise
            finally:
                self._local.active = False
