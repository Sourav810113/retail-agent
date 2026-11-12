from __future__ import annotations

from uuid import uuid4

from ..core.clock import Clock
from ..core.db import UnitOfWork
from ..domain.audit_details import AUDIT_CONTRACT, AuditDetails
from ..domain.enums import ActionType, Outcome
from ..domain.models import AuditEvent
from ..repositories.audit_repository import AuditRepository


class AuditService:
    """The only writer of Audit Events (AD-4). Never opens a transaction."""

    def __init__(
        self, uow: UnitOfWork, clock: Clock, repository: AuditRepository | None = None
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._repository = repository or AuditRepository(uow)

    def record(
        self,
        action: ActionType,
        outcome: Outcome,
        details: AuditDetails,
        order_id: str | None = None,
        return_id: str | None = None,
    ) -> AuditEvent:
        if not self._uow.in_transaction:
            raise RuntimeError("AuditService.record must run inside a transaction")
        allowed_outcomes, details_model = AUDIT_CONTRACT[action]
        if outcome not in allowed_outcomes:
            raise ValueError(f"outcome {outcome.value!r} is not valid for {action.value}")
        if type(details) is not details_model:
            raise TypeError(f"{action.value} requires {details_model.__name__}")
        event = AuditEvent(
            event_id=str(uuid4()),
            occurred_at=self._clock.now(),
            action=action,
            outcome=outcome,
            order_id=order_id,
            return_id=return_id,
            details_json=details.model_dump_json(),
        )
        self._repository.insert(event)
        return event
