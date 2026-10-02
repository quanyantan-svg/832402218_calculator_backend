# Calculator Backend

Backend service for the Front-End and Back-End Separation Calculator System.

This repository provides the FastAPI application skeleton, the MySQL
connection layer, the safe mathematical expression parser, and the
calculation API. The history-query and history-delete endpoints are
scheduled for a later phase.

## Tech Stack

- Python 3.13
- FastAPI 0.142
- SQLAlchemy 2.x (synchronous)
- PyMySQL driver
- MySQL 8.0
- pydantic-settings for configuration
- pytest for testing

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── exceptions.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── calculation_history.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── calculator.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── calculator_service.py
│   │   └── expression_parser.py
│   └── api/
│       ├── __init__.py
│       └── routes/
│           ├── __init__.py
│           └── calculator.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_expression_parser.py
│   ├── test_decimal_normalization.py
│   ├── test_calculator_service.py
│   └── test_calculate_api.py
├── .env.example
├── .gitignore
├── codestyle.md
├── requirements.txt
└── README.md
```

## Configuration

Copy `.env.example` to `.env` and fill in the local MySQL credentials. The
`.env` file must never be committed. All credentials are loaded via
`pydantic-settings` and the SQLAlchemy URL is built programmatically with
`sqlalchemy.engine.URL.create()`.

## Install

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
uvicorn app.main:app --reload
```

The Swagger UI is available at:

- http://127.0.0.1:8000/docs

The health endpoint:

- http://127.0.0.1:8000/health

The calculation endpoint:

- `POST http://127.0.0.1:8000/api/calculate`

## Expression Parser

The calculator uses a safe recursive-descent parser implemented in
`app/services/expression_parser.py`. It accepts the grammar:

```
expression = term (("+" | "-") term)*
term       = unary (("*" | "/") unary)*
unary      = ("+" | "-") unary | primary
primary    = NUMBER | "(" expression ")"
```

A `NUMBER` is a non-negative decimal literal in forms such as `0`, `123`,
`3.14`, `.5`, and `5.`.

### Supported Features

- The four basic arithmetic operators: `+`, `-`, `*`, `/`.
- Standard operator precedence (`*` and `/` bind tighter than `+` and `-`)
  with left-associativity.
- Parentheses, including nested parentheses.
- Unary `+` and `-`, including chained forms like `--5` and `-(1+2)`.
- Arbitrary whitespace between tokens.

### Arithmetic

All arithmetic uses `decimal.Decimal` so values such as `0.1 + 0.2` are
computed as exactly `0.3` rather than through floating-point.

### Safety

The parser does not use `eval`, `exec`, `compile`, or any equivalent
mechanism. The full grammar is hand-written and only accepts the
non-terminals listed above. Any input that does not match the grammar is
rejected as `InvalidExpressionError`. Division by zero raises
`DivisionByZeroError`. Both exceptions subclass `CalculatorError`.

The parser enforces a maximum input length of `MAX_EXPRESSION_LENGTH = 1024`
characters, matching the width of the `calculation_history.expression`
column. Inputs longer than the limit, deeply nested expressions, and
non-string inputs are all rejected with `InvalidExpressionError` so that no
internal Python exception leaks to the API layer.

## Calculation API

### `POST /api/calculate`

The calculation endpoint accepts a JSON body, evaluates the expression on
the backend, persists the result, and returns it as a JSON string.

Request body:

```
{
    "expression": "(1+2)*3"
}
```

Successful response (`HTTP 200 OK`):

```
{
    "success": true,
    "expression": "(1+2)*3",
    "result": "9"
}
```

Error response for a bad expression or division by zero (`HTTP 400`):

```
{
    "success": false,
    "message": "division by zero"
}
```

Server-error response (`HTTP 500`) when persistence fails:

```
{
    "success": false,
    "message": "Internal server error"
}
```

### Behavior

- The frontend never computes the final result; the backend does.
- Every successful calculation is persisted as one row in
  `calculation_history` before the API returns a successful response.
- Invalid expressions and division-by-zero do not create any database row.
- The `result` field is always a string so that exact decimal output (for
  example `"0.3"` for `0.1 + 0.2`) survives transport without
  floating-point conversion.

## Database

The MySQL schema is created on application startup via
`Base.metadata.create_all()`. Only one table exists at this stage:

- `calculation_history`

| column       | type           | notes                          |
|--------------|----------------|--------------------------------|
| id           | INT            | PK, auto increment             |
| expression   | VARCHAR(1024)  | NOT NULL                        |
| result       | VARCHAR(1024)  | NOT NULL, stored as text       |
| created_at   | DATETIME       | NOT NULL, server-side default  |

The `result` column is stored as text. Calculated values such as `0.1 +
0.2` are stored in their canonical decimal form (for example `"0.3"`), not
as the original expression.

## CORS

The local Vue / Vite development origins are allowed:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Health Check

`GET /health` runs a lightweight `SELECT 1` against the database. The
response reports the application name, environment, and whether the
database is reachable. Database credentials and connection details are
never exposed in the response body.

## Testing

Run the full test suite:

```
pytest -v
```

Parser-specific tests live in `tests/test_expression_parser.py`. Service-
and API-level tests use an in-memory SQLite database via a `get_db`
dependency override so the automated suite does not require a running
local MySQL instance.
