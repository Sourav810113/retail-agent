from decimal import Decimal

import pytest

from src.retail_agent.domain.money import (
    cents_to_decimal,
    decimal_to_cents,
    format_money,
    quantize,
)


def test_cents_round_trip():
    assert cents_to_decimal(8999) == Decimal("89.99")
    assert decimal_to_cents(Decimal("89.99")) == 8999
    assert cents_to_decimal(0) == Decimal("0.00")


def test_quantize_rounds_half_up():
    assert quantize(Decimal("0.005")) == Decimal("0.01")
    assert quantize(Decimal("2.675")) == Decimal("2.68")
    assert decimal_to_cents(Decimal("12.345")) == 1235


def test_format_money_always_two_places():
    assert format_money(Decimal("40")) == "40.00"
    assert format_money(Decimal("39.98")) == "39.98"
    assert format_money(cents_to_decimal(5)) == "0.05"


@pytest.mark.parametrize("bad", [1.5, "1.50", 2])
def test_decimal_to_cents_rejects_non_decimal(bad):
    with pytest.raises(TypeError):
        decimal_to_cents(bad)


@pytest.mark.parametrize("bad", [Decimal("NaN"), Decimal("Infinity")])
def test_quantize_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        quantize(bad)


@pytest.mark.parametrize("bad", [True, 1.0, "100"])
def test_cents_to_decimal_rejects_non_int(bad):
    with pytest.raises(TypeError):
        cents_to_decimal(bad)
