"""Dependencies: clock and uow from app.state, services built per request."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from ..core.clock import Clock
from ..core.db import UnitOfWork
from ..services.audit_service import AuditService
from ..services.health_service import HealthService
from ..services.order_service import OrderService


def get_clock(request: Request) -> Clock:
    return request.app.state.clock


def get_uow(request: Request) -> UnitOfWork:
    return request.app.state.uow


def get_audit_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)], clock: Annotated[Clock, Depends(get_clock)]
) -> AuditService:
    return AuditService(uow, clock)


def get_order_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> OrderService:
    return OrderService(uow, audit)


def get_health_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> HealthService:
    return HealthService(uow)
