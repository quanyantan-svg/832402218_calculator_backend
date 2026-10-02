# Calculator Backend

Backend service for the Front-End and Back-End Separation Calculator System.

This repository provides the FastAPI application skeleton, the MySQL
connection layer, and the safe mathematical expression parser that powers
calculation. The `/api/calculate`, `/api/history`, and `/api/history/{id}`
endpoints are scheduled for a later phase.

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
│   │   └── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── expression_parser.py
│   └── api/
│       ├── __init__.py
│       └── routes/
│           └── __init__.py
├── tests/
│   ├── __init__.py
│   └── test_expression_parser.py
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

Parser-specific tests live in `tests/test_expression_parser.py` and can be
run directly:

```
pytest -v tests/test_expression_parser.py
```
