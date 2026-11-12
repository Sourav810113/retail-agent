"""Money helpers (AD-5): Decimal in the domain, INTEGER cents in SQLite."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def quantize(amount: Decimal) -> Decimal:
    """Round to 2 decimal places, half up."""
    if not isinstance(amount, Decimal):
        raise TypeError("money amounts must be Decimal")
    if not amount.is_finite():
        raise ValueError("money amounts must be finite")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def cents_to_decimal(cents: int) -> Decimal:
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError("cents must be an int")
    return (Decimal(cents) / 100).quantize(CENT)


def decimal_to_cents(amount: Decimal) -> int:
    return int(quantize(amount) * 100)


def format_money(amount: Decimal) -> str:
    """The 2-decimal-place JSON string form, e.g. ``"40.00"``."""
    return f"{quantize(amount):.2f}"
