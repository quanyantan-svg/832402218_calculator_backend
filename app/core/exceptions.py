"""Domain exceptions for the calculator backend."""


class CalculatorError(Exception):
    """Base class for all calculator-domain errors."""


class InvalidExpressionError(CalculatorError):
    """Raised when an input cannot be parsed as a valid expression."""


class DivisionByZeroError(CalculatorError):
    """Raised when evaluation requires division by zero."""


class PersistenceError(CalculatorError):
    """Raised when a calculation result cannot be persisted to storage."""


class HistoryReadError(CalculatorError):
    """Raised when reading calculation history from storage fails."""
