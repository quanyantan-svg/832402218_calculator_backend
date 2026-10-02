# Calculator Backend

Backend service for the Front-End and Back-End Separation Calculator System.

This repository provides the FastAPI application skeleton, the MySQL
connection layer, the safe mathematical expression parser, the
calculation API, and the calculation history API. The backend
currently supports safe expression calculation, MySQL persistence,
history retrieval, and deletion of an individual history record.

## Tech Stack

- Python 3.13 (development)
- Python 3.12 (production deployment)
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
│   │   ├── calculator.py
│   │   └── history.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── calculator_service.py
│   │   ├── expression_parser.py
│   │   └── history_service.py
│   └── api/
│       ├── __init__.py
│       └── routes/
│           ├── __init__.py
│           ├── calculator.py
│           └── history.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_expression_parser.py
│   ├── test_decimal_normalization.py
│   ├── test_calculator_service.py
│   ├── test_calculate_api.py
│   ├── test_history_service.py
│   ├── test_history_api.py
│   └── test_history_delete_api.py
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

Local Windows development:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux production note:

```
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

```
uvicorn app.main:app --reload
```

The Swagger UI is available at:

- http://127.0.0.1:8000/docs

The implemented endpoints:

- `GET    http://127.0.0.1:8000/health`
- `POST   http://127.0.0.1:8000/api/calculate`
- `GET    http://127.0.0.1:8000/api/history`
- `DELETE http://127.0.0.1:8000/api/history/{history_id}`

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

## History API

### `GET /api/history`

The history endpoint returns every successfully persisted calculation,
ordered newest first. The response is read directly from the backend
database; no in-memory or client-side cache is involved.

Successful response (`HTTP 200 OK`) with at least one row:

```
{
    "success": true,
    "history": [
        {
            "id": 3,
            "expression": "(1+2)*3",
            "result": "9",
            "created_at": "2026-10-02T17:30:00"
        }
    ]
}
```

Empty response (`HTTP 200 OK`):

```
{
    "success": true,
    "history": []
}
```

Server-error response (`HTTP 500`) on a database read failure:

```
{
    "success": false,
    "message": "Internal server error"
}
```

### Behavior

- Ordering is `ORDER BY calculation_history.id DESC` so the newest
  calculation is always returned first. Ordering by primary key is used
  rather than `created_at` because multiple rows may share the same
  timestamp resolution.
- Each item exposes `id`, `expression`, `result`, and `created_at`.
- `created_at` is serialized as an ISO-8601 datetime string.
- The endpoint is read-only. It does not insert, update, or delete rows
  and does not commit a transaction.
- The backend MySQL database is the source of truth. History committed
  by `POST /api/calculate` remains visible to subsequent
  `GET /api/history` requests — including requests issued from a fresh
  HTTP client or after the application is restarted — because the rows
  are persisted in MySQL, not in application memory.
- Invalid calculations are never stored, so they never appear in
  history.

## History Deletion

### `DELETE /api/history/{history_id}`

The deletion endpoint removes a single history record from the backend
database. The path parameter is the primary-key `id` returned by
`GET /api/history`.

Successful response (`HTTP 200 OK`):

```
{
    "success": true,
    "message": "History record deleted"
}
```

Not-found response (`HTTP 404`):

```
{
    "success": false,
    "message": "History record not found"
}
```

Database-error response (`HTTP 500`):

```
{
    "success": false,
    "message": "Internal server error"
}
```

A non-integer path parameter (for example `/api/history/abc`) is
rejected by FastAPI/Pydantic with a client-error response and a
generic `"Invalid request"` body. Deletion is never performed on
malformed input.

### Behavior

- The route looks up the row by primary key first. If the row is
  missing, `404` is returned without touching the database write path.
- When the row exists, the service issues `DELETE` and commits in the
  same transaction. The API does not report success until the commit
  succeeds. If the commit fails, the session is rolled back and the
  response is a sanitized `500`.
- Deletion is performed against MySQL and remains effective after the
  client refreshes or restarts — the deleted record stays absent from
  subsequent `GET /api/history` responses because it is no longer in
  the database.
- Deletion removes only the specified row. Other rows are untouched.
- There is intentionally no clear-all or batch-delete endpoint in this
  phase.

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

In production the deployed frontend and API are served through the same
public Nginx origin, so production browser requests use the Nginx
endpoint rather than calling `127.0.0.1:8000` directly.

## Health Check

`GET /health` runs a lightweight `SELECT 1` against the database. The
response reports the application name, environment, and whether the
database is reachable. Database credentials and connection details are
never exposed in the response body.

## Production Deployment

The backend is deployed on Tencent Cloud Lighthouse (Ubuntu) and
managed as a systemd service. Nginx is the public-facing reverse proxy;
FastAPI is bound to the loopback interface only and is not exposed to
the public network.

### Public Deployment

Public calculator URL:

- `http://129.204.51.149:8082`

Users do not access the FastAPI port `8000` directly. Nginx accepts
public traffic and reverse-proxies API requests to the local FastAPI
instance.

### Production Architecture

```
Internet
   |
   v
Nginx  :8082   (public)
   |
   |-- /api/*  --> FastAPI  127.0.0.1:8000
   |-- /health --> FastAPI  127.0.0.1:8000
   |
   '-- /       --> static frontend at /var/www/calculator

FastAPI  127.0.0.1:8000
   |
   v
MySQL  127.0.0.1:3306  (database: calculator_db)
```

The Vue frontend is also served by Nginx from
`/var/www/calculator`. The backend working directory on the server is
`/opt/calculator/backend`.

### Production Configuration

The production configuration is loaded from the server-side `.env`
file (not committed to Git). The conceptual keys are:

```
APP_ENV=production
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=calculator_db
```

`DB_USER` and `DB_PASSWORD` are stored in the server-side `.env` and
are not committed to this repository. No real credentials appear in
this README or in any tracked file.

### systemd

The backend is managed by the systemd unit:

- `calculator-backend.service`

The effective service command is:

```
/opt/calculator/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Notes:

- The service is enabled at boot.
- `Restart=on-failure` is configured so the backend restarts after
  crashes.
- Backend startup after a server reboot has been verified.

Useful administrative commands:

```
sudo systemctl status calculator-backend
sudo systemctl restart calculator-backend
sudo journalctl -u calculator-backend -n 100 --no-pager
```

### Nginx / Network Boundary

- Nginx public port for this project: `8082`.
- FastAPI port `8000` is loopback-only (`127.0.0.1`).
- MySQL port `3306` is local-only and is not intentionally exposed to
  the public network.
- The Tencent Cloud Lighthouse firewall allows the project's public
  web port (`8082`).
- Application and database internal ports are not intended for direct
  public access.

### Production Verification

The following facts were verified against the live deployment:

- `GET /health` returns `status: healthy`.
- `app.env` is reported as `production`.
- `database.connected` is `true`.
- `POST /api/calculate` works through the public deployment.
- `GET /api/history` works through the public deployment.
- `DELETE /api/history/{id}` works through the public deployment.
- MySQL persistence survives backend and server restart.
- systemd, Nginx, and MySQL recovered after a server reboot.
- The deployed calculator remained usable after restart.

HTTPS is not configured for this deployment, and no domain name is
attached to the public IP at this stage.

## Security

Production secrets (database credentials, SSH keys, tokens, and the
full `.env` contents) are stored only on the server and are not
committed to this repository. No real credentials appear in this
README, in `.env.example`, or in any tracked source file.

## Testing

Run the full test suite:

```
pytest -v
```

Parser-specific tests live in `tests/test_expression_parser.py`. Service-
and API-level tests use an in-memory SQLite database that fully
replaces the production MySQL engine for the duration of the test
session (lifespan, ``/health``, and request handlers). The normal
automated suite therefore does not require a running local MySQL
instance.
