from __future__ import annotations

from ..core.db import UnitOfWork


class HealthRepository:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def ping(self) -> None:
        """Read from the data store; raises ``sqlite3.Error`` if it cannot."""
        self._uow.connection.execute("SELECT 1 FROM products LIMIT 1").fetchall()
