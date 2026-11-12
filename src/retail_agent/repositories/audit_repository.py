from __future__ import annotations

from ..core.clock import format_ts
from ..core.db import UnitOfWork
from ..domain.models import AuditEvent


class AuditRepository:
    """Insert-only (FR-13): there is deliberately no update or delete."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def insert(self, event: AuditEvent) -> None:
        self._uow.connection.execute(
            "INSERT INTO audit_events"
            " (event_id, occurred_at, action, outcome, order_id, return_id, details_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                format_ts(event.occurred_at),
                event.action.value,
                event.outcome.value,
                event.order_id,
                event.return_id,
                event.details_json,
            ),
        )
