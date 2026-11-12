"""All domain enums (AD-10: the single owner of enum definitions)."""

from enum import StrEnum


class OrderStatus(StrEnum):
    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ActionType(StrEnum):
    ORDER_LOOKUP = "ORDER_LOOKUP"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    REFUND_CALCULATED = "REFUND_CALCULATED"
    INVENTORY_RESTOCKED = "INVENTORY_RESTOCKED"
    RETURN_VIEWED = "RETURN_VIEWED"


class Outcome(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    ACCEPTED = "accepted"
    DENIED = "denied"
    RECORDED = "recorded"


class DenialReason(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    ORDER_NOT_DELIVERED = "ORDER_NOT_DELIVERED"
    RETURN_WINDOW_EXPIRED = "RETURN_WINDOW_EXPIRED"
    ITEM_NOT_ON_ORDER = "ITEM_NOT_ON_ORDER"
    ITEM_NOT_RETURNABLE = "ITEM_NOT_RETURNABLE"
    QUANTITY_EXCEEDS_RETURNABLE = "QUANTITY_EXCEEDS_RETURNABLE"
