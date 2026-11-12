"""API schemas (AD-10: the single owner of request/response models)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from ..domain.enums import OrderStatus

MONEY_PATTERN = r"^-?\d+\.\d{2}$"


class LineView(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_price: str = Field(pattern=MONEY_PATTERN, examples=["39.98"])
    quantity_returned: int


class ReturnSummary(BaseModel):
    return_id: str
    refund_amount: str = Field(pattern=MONEY_PATTERN, examples=["39.98"])
    created_at: str


class OrderView(BaseModel):
    order_id: str
    status: OrderStatus
    order_date: date
    delivery_date: date | None
    return_eligible_until: date | None
    lines: list[LineView]
    returns: list[ReturnSummary]


class HealthView(BaseModel):
    status: Literal["ok"]


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
