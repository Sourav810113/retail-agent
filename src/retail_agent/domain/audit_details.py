"""Typed details payloads for Audit Events (AD-4).

None of these models has an email field, and ``extra="forbid"`` stops one
being smuggled in.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from .enums import ActionType, DenialReason, Outcome
from .money import quantize


class _Details(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OrderLookupDetails(_Details):
    pass


class ReturnRequestedDetails(_Details):
    line_count: int
    denial_reason: DenialReason | None = None


class RefundCalculatedDetails(_Details):
    refund_amount: Decimal

    @field_validator("refund_amount")
    @classmethod
    def _two_places(cls, value: Decimal) -> Decimal:
        return quantize(value)


class InventoryRestockedDetails(_Details):
    sku: str
    quantity: int


class ReturnViewedDetails(_Details):
    pass


AuditDetails = (
    OrderLookupDetails
    | ReturnRequestedDetails
    | RefundCalculatedDetails
    | InventoryRestockedDetails
    | ReturnViewedDetails
)

# The AD-4 table: which outcomes and details model each action allows.
AUDIT_CONTRACT: dict[ActionType, tuple[frozenset[Outcome], type[_Details]]] = {
    ActionType.ORDER_LOOKUP: (frozenset({Outcome.FOUND, Outcome.NOT_FOUND}), OrderLookupDetails),
    ActionType.RETURN_REQUESTED: (
        frozenset({Outcome.ACCEPTED, Outcome.DENIED}),
        ReturnRequestedDetails,
    ),
    ActionType.REFUND_CALCULATED: (frozenset({Outcome.RECORDED}), RefundCalculatedDetails),
    ActionType.INVENTORY_RESTOCKED: (frozenset({Outcome.RECORDED}), InventoryRestockedDetails),
    ActionType.RETURN_VIEWED: (frozenset({Outcome.FOUND, Outcome.NOT_FOUND}), ReturnViewedDetails),
}
