from __future__ import annotations

import logging
import sqlite3

from ..core.db import UnitOfWork
from ..domain.errors import ServiceUnavailableError
from ..repositories.health_repository import HealthRepository

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, uow: UnitOfWork, repository: HealthRepository | None = None) -> None:
        self._uow = uow
        self._repository = repository or HealthRepository(uow)

    def check(self) -> None:
        """Entry point for FR-14. Raises ServiceUnavailableError if the store is unreadable."""
        try:
            with self._uow.transaction():
                self._repository.ping()
        except sqlite3.Error as exc:
            logger.warning("health check failed: %s", type(exc).__name__)
            raise ServiceUnavailableError() from exc
