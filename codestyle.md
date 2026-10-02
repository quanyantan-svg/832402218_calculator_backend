# Code Style

This project follows PEP 8 with the conventions listed below.

## Formatting

- 4 spaces per indentation level, no tabs.
- Maximum line length of 100 characters where reasonable.
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

## Docstrings

- One-line docstring for short, obvious modules, functions, and classes.
- Full docstrings are reserved for non-trivial public APIs.

## Tests

- Tests live under `tests/` and are written with `pytest`.
- Test files are named `test_*.py`.
- Tests should be deterministic and not depend on external services
  unless explicitly designed as integration tests.
