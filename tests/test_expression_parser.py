"""Tests for the safe expression parser."""

from decimal import Decimal

import pytest

from app.core.exceptions import (
    CalculatorError,
    DivisionByZeroError,
    InvalidExpressionError,
)
from app.services.expression_parser import (
    MAX_EXPRESSION_LENGTH,
    parse_and_calculate,
)


def _calculate(expression):
    """Convenience wrapper that calls the parser and returns the result."""
    return parse_and_calculate(expression)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1+2", Decimal("3")),
        ("5-8", Decimal("-3")),
        ("4*3", Decimal("12")),
        ("8/2", Decimal("4")),
        ("0+0", Decimal("0")),
    ],
)
def test_basic_arithmetic(expression: str, expected: Decimal) -> None:
    assert _calculate(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1+2*3", Decimal("7")),
        ("8-3*2", Decimal("2")),
        ("10/2+7", Decimal("12")),
        ("1*2+3*4", Decimal("14")),
    ],
)
def test_operator_precedence(expression: str, expected: Decimal) -> None:
    assert _calculate(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(1+2)*3", Decimal("9")),
        ("2*(3+(4*5))", Decimal("46")),
        ("(10)", Decimal("10")),
        ("((1+2)*(3+4))", Decimal("21")),
        ("(1+2)*(3+4)", Decimal("21")),
    ],
)
def test_parentheses(expression: str, expected: Decimal) -> None:
    assert _calculate(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("10-3-2", Decimal("5")),
        ("8/4/2", Decimal("1")),
        ("20-5-3-2", Decimal("10")),
        ("100/2/5", Decimal("10")),
    ],
)
def test_left_associativity(expression: str, expected: Decimal) -> None:
    assert _calculate(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("-5+8", Decimal("3")),
        ("3*-2", Decimal("-6")),
        ("3--2", Decimal("5")),
        ("-(1+2)", Decimal("-3")),
        ("+5", Decimal("5")),
        ("3*+2", Decimal("6")),
        ("--5", Decimal("5")),
        ("-+5", Decimal("-5")),
        ("+-5", Decimal("-5")),
        ("++5", Decimal("5")),
    ],
)
def test_unary_operators(expression: str, expected: Decimal) -> None:
    assert _calculate(expression) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("0.1+0.2", Decimal("0.3")),
        ("1.5*2", Decimal("3.0")),
        ("10/4", Decimal("2.5")),
        (".5+.25", Decimal("0.75")),
        ("5.+0.5", Decimal("5.5")),
        ("3.14", Decimal("3.14")),
        ("0.5", Decimal("0.5")),
        ("0", Decimal("0")),
        ("123", Decimal("123")),
    ],
)
def test_decimal_numbers(expression: str, expected: Decimal) -> None:
    assert _calculate(expression) == expected


def test_decimal_result_type() -> None:
    """The parser must return ``Decimal``, not ``float``."""
    result = _calculate("1+2")
    assert isinstance(result, Decimal)


def test_whitespace_tolerance() -> None:
    assert _calculate(" 1 + 2 * 3 ") == Decimal("7")
    assert _calculate("1+2") == _calculate("  1  +  2  ")


@pytest.mark.parametrize(
    "expression",
    [
        "1/0",
        "1/(2-2)",
        "5/(3-3)",
        "(1+1)/(0)",
    ],
)
def test_division_by_zero(expression: str) -> None:
    with pytest.raises(DivisionByZeroError):
        _calculate(expression)


def test_division_by_zero_is_calculator_error() -> None:
    with pytest.raises(CalculatorError):
        _calculate("1/0")


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "   ",
        "\t\n",
        "1+",
        "*2",
        "1**2",
        "1//2",
        "(1+2",
        "1+2)",
        "1 2",
        "abc",
        "1+abc",
        "()",
        ".",
        "1..2",
        "2(3+4)",
        "(1+2)(3+4)",
        "+",
        "-",
        "( )",
        "(+)",
        "1+2+",
        "1++",
    ],
)
def test_invalid_expressions(expression: str) -> None:
    with pytest.raises(InvalidExpressionError):
        _calculate(expression)


def test_invalid_expression_is_calculator_error() -> None:
    with pytest.raises(CalculatorError):
        _calculate("1+")


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os")',
        'open("file")',
        "1;2",
        "1,2",
        "1+2;print('x')",
        "x=1",
        "lambda x: x",
        "[1,2,3]",
        "{1:2}",
        '"hello"',
        "'hello'",
    ],
)
def test_code_like_strings_rejected(expression: str) -> None:
    with pytest.raises(InvalidExpressionError):
        _calculate(expression)


@pytest.mark.parametrize("operator", ["**", "//", "%", "@", "&", "|", "^", "~"])
def test_unsupported_operators_rejected(operator: str) -> None:
    with pytest.raises(InvalidExpressionError):
        _calculate(f"1{operator}2")


def test_result_is_consumed_fully_or_rejected() -> None:
    """Trailing content after a complete expression must be rejected."""
    with pytest.raises(InvalidExpressionError):
        _calculate("1+2 3")
    with pytest.raises(InvalidExpressionError):
        _calculate("(1+2) 3")


def test_non_string_input_rejected() -> None:
    """Non-string direct service input must not leak a Python ``TypeError``."""
    for value in [None, 42, 3.14, [], {}, object()]:
        with pytest.raises(InvalidExpressionError):
            _calculate(value)


def test_expression_length_limit_constant_exposed() -> None:
    """The limit constant must match the database column width."""
    assert MAX_EXPRESSION_LENGTH == 1024


def test_expression_longer_than_limit_rejected() -> None:
    long_expression = "1+" * (MAX_EXPRESSION_LENGTH // 2) + "1"
    if len(long_expression) <= MAX_EXPRESSION_LENGTH:
        long_expression += " " * (MAX_EXPRESSION_LENGTH + 1 - len(long_expression))
    assert len(long_expression) > MAX_EXPRESSION_LENGTH
    with pytest.raises(InvalidExpressionError):
        _calculate(long_expression)


def test_deeply_nested_expression_rejected_cleanly() -> None:
    """Deep nesting must not leak a Python ``RecursionError``."""
    depth = 400
    expression = "(" * depth + "1" + ")" * depth
    with pytest.raises(InvalidExpressionError):
        _calculate(expression)


def test_exception_messages_do_not_leak_python_internals() -> None:
    """Error messages should be readable and not expose stack frames."""
    try:
        _calculate("1+")
    except InvalidExpressionError as exc:
        assert "Traceback" not in str(exc)
    else:
        pytest.fail("expected InvalidExpressionError")
