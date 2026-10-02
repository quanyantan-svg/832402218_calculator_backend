# Code Style

The backend code standard is based on:

**PEP 8 — Style Guide for Python Code**

Source: https://peps.python.org/pep-0008/

This document lists the conventions used in this project. Where a project
convention intentionally deviates from the PEP 8 default (for example the
100-character line length described below), it is noted as such and is
not a redefinition of the standard itself.

## Formatting

- 4 spaces per indentation level, no tabs.
- Maximum line length of **100 characters**. This is a practical project
  convention that is more permissive than the PEP 8 default of 79; it is
  not the PEP 8 default.
- One statement per line.
- Two blank lines between top-level definitions, one blank line between
  methods inside a class.
- File encoding is UTF-8, line endings are LF.

## Imports

- Imports are grouped in the order: standard library, third-party, local.
- Each group is separated by a single blank line.
- Absolute imports are preferred.

## Naming

- `snake_case` for functions, methods, variables, and module names.
- `PascalCase` for classes and Pydantic models.
- `UPPER_SNAKE_CASE` for module-level constants.
- SQLAlchemy models use singular nouns (`CalculationHistory`).

## Type Hints

- Type hints are used on public functions and methods.
- SQLAlchemy 2.x `Mapped[...]` annotations are used for ORM columns.

## Logging and Errors

- Logging is done through the `logging` module, not `print`.
- Sensitive values such as database passwords are never logged or
  returned in HTTP responses.
- Domain-level errors are raised through dedicated exception types in
  `app/core/exceptions.py` so that no internal Python exception type
  (such as `TypeError`, `RecursionError`, or `decimal.InvalidOperation`)
  leaks to API callers.

## Docstrings

- One-line docstring for short, obvious modules, functions, and classes.
- Full docstrings are reserved for non-trivial public APIs.

## Tests

- Tests live under `tests/` and are written with `pytest`.
- Test files are named `test_*.py`.
- Tests should be deterministic and not depend on external services
  unless explicitly designed as integration tests.
