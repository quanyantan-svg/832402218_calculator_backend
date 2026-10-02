"""Tests for the Decimal result normalization helper."""

from decimal import Decimal

import pytest

from app.services.calculator_service import normalize_decimal


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("3.00"), "3"),
        (Decimal("0.300"), "0.3"),
        (Decimal("-0"), "0"),
        (Decimal("2.5"), "2.5"),
        (Decimal("0.1"), "0.1"),
        (Decimal("1"), "1"),
        (Decimal("-3"), "-3"),
        (Decimal("100"), "100"),
        (Decimal("0.10"), "0.1"),
        (Decimal("1E+2"), "100"),
    ],
)
def test_normalize_decimal(value: Decimal, expected: str) -> None:
    assert normalize_decimal(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("-0.0"), "0"),
        (Decimal("0E+10"), "0"),
        (Decimal("-0E+5"), "0"),
    ],
)
def test_normalize_decimal_signed_zero(value: Decimal, expected: str) -> None:
    assert normalize_decimal(value) == expected


def test_normalize_decimal_strips_trailing_zeros_only() -> None:
    """The helper must not lose precision while removing trailing zeros."""
    assert normalize_decimal(Decimal("1.2345000")) == "1.2345"
    assert normalize_decimal(Decimal("1234500")) == "1234500"
