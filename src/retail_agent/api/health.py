from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..services.health_service import HealthService
from .deps import get_health_service
from .errors import ERROR_RESPONSES
from .schemas import HealthView

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthView, responses=ERROR_RESPONSES, summary="Health check")
def healthz(service: Annotated[HealthService, Depends(get_health_service)]) -> HealthView:
    service.check()
    return HealthView(status="ok")
