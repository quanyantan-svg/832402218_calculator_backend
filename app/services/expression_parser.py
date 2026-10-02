"""Safe recursive-descent parser for mathematical expressions.

The grammar is:

    expression = term (("+" | "-") term)*
    term       = unary (("*" | "/") unary)*
    unary      = ("+" | "-") unary | primary
    primary    = NUMBER | "(" expression ")"

A ``NUMBER`` is a non-negative decimal literal that supports forms such as
``0``, ``123``, ``3.14``, ``.5`` and ``5.``. Arithmetic uses
:class:`decimal.Decimal` for exact decimal results.
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.core.exceptions import DivisionByZeroError, InvalidExpressionError


MAX_EXPRESSION_LENGTH = 1024


class _TokenKind(str, Enum):
    NUMBER = "NUMBER"
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"


@dataclass(frozen=True)
class _Token:
    kind: _TokenKind
    value: Decimal | None
    position: int


def parse_and_calculate(expression: str) -> Decimal:
    """Parse and evaluate ``expression``, returning the :class:`Decimal` result.

    The parser accepts the grammar documented in the module docstring and
    raises :class:`InvalidExpressionError` or :class:`DivisionByZeroError`
    on bad input. The full input is consumed; trailing garbage is rejected.

    Non-string input is rejected with :class:`InvalidExpressionError` rather
    than leaking a Python ``TypeError``.
    """
    if not isinstance(expression, str):
        raise InvalidExpressionError(
            f"expression must be a string, got {type(expression).__name__}"
        )
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise InvalidExpressionError(
            f"expression exceeds maximum length of {MAX_EXPRESSION_LENGTH}"
        )

    tokens = _tokenize(expression)
    if not tokens:
        raise InvalidExpressionError("empty expression")

    parser = _Parser(tokens)
    try:
        result = parser._expression()
    except RecursionError as exc:
        raise InvalidExpressionError("expression is too deeply nested") from exc

    if parser._peek() is not None:
        trailing = parser._peek()
        raise InvalidExpressionError(
            f"unexpected token after expression at position {trailing.position}"
        )
    return result


def _tokenize(text: str) -> list[_Token]:
    """Convert ``text`` into a flat list of tokens.

    Whitespace is skipped. Anything that is not whitespace, a digit, ``.``,
    or one of ``+-*/()`` is rejected as an invalid character.
    """
    tokens: list[_Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
            continue
        if ch == "+":
            tokens.append(_Token(_TokenKind.PLUS, None, i))
            i += 1
            continue
        if ch == "-":
            tokens.append(_Token(_TokenKind.MINUS, None, i))
            i += 1
            continue
        if ch == "*":
            tokens.append(_Token(_TokenKind.STAR, None, i))
            i += 1
            continue
        if ch == "/":
            tokens.append(_Token(_TokenKind.SLASH, None, i))
            i += 1
            continue
        if ch == "(":
            tokens.append(_Token(_TokenKind.LPAREN, None, i))
            i += 1
            continue
        if ch == ")":
            tokens.append(_Token(_TokenKind.RPAREN, None, i))
            i += 1
            continue
        if ch.isdigit() or ch == ".":
            j = i
            has_digit = False
            has_dot = False
            while j < n and (text[j].isdigit() or text[j] == "."):
                if text[j] == ".":
                    if has_dot:
                        raise InvalidExpressionError(
                            f"malformed number near position {j}"
                        )
                    has_dot = True
                else:
                    has_digit = True
                j += 1
            if not has_digit:
                raise InvalidExpressionError(
                    f"malformed number near position {i}"
                )
            literal = text[i:j]
            try:
                value = Decimal(literal)
            except decimal.InvalidOperation as exc:
                raise InvalidExpressionError(
                    f"invalid number literal {literal!r}"
                ) from exc
            tokens.append(_Token(_TokenKind.NUMBER, value, i))
            i = j
            continue
        raise InvalidExpressionError(
            f"unexpected character {ch!r} at position {i}"
        )
    return tokens


class _Parser:
    """Recursive-descent parser that consumes a flat token stream.

    The method names mirror the grammar non-terminals.
    """

    __slots__ = ("_tokens", "_pos")

    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> _Token | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _consume(self) -> _Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _expression(self) -> Decimal:
        """``expression = term (("+" | "-") term)*``"""
        left = self._term()
        while True:
            token = self._peek()
            if token is None or token.kind not in (_TokenKind.PLUS, _TokenKind.MINUS):
                return left
            op = self._consume()
            right = self._term()
            if op.kind == _TokenKind.PLUS:
                left = left + right
            else:
                left = left - right

    def _term(self) -> Decimal:
        """``term = unary (("*" | "/") unary)*``"""
        left = self._unary()
        while True:
            token = self._peek()
            if token is None or token.kind not in (_TokenKind.STAR, _TokenKind.SLASH):
                return left
            op = self._consume()
            right = self._unary()
            if op.kind == _TokenKind.STAR:
                left = left * right
            else:
                if right == 0:
                    raise DivisionByZeroError("division by zero")
                left = left / right

    def _unary(self) -> Decimal:
        """``unary = ("+" | "-") unary | primary``"""
        token = self._peek()
        if token is not None and token.kind in (_TokenKind.PLUS, _TokenKind.MINUS):
            op = self._consume()
            operand = self._unary()
            if op.kind == _TokenKind.MINUS:
                return -operand
            return operand
        return self._primary()

    def _primary(self) -> Decimal:
        """``primary = NUMBER | "(" expression ")"``"""
        token = self._peek()
        if token is None:
            raise InvalidExpressionError("expected number or '('")
        if token.kind == _TokenKind.NUMBER:
            self._consume()
            assert token.value is not None
            return token.value
        if token.kind == _TokenKind.LPAREN:
            self._consume()
            value = self._expression()
            closer = self._peek()
            if closer is None or closer.kind != _TokenKind.RPAREN:
                raise InvalidExpressionError("expected ')'")
            self._consume()
            return value
        raise InvalidExpressionError(
            f"unexpected token {token.kind.name} at position {token.position}"
        )
