# Calculator Backend

Backend service for the Front-End and Back-End Separation Calculator System.

This repository currently provides the FastAPI application skeleton and the
MySQL connection layer. The expression parser and the
`/api/calculate`, `/api/history`, and `/api/history/{id}` endpoints will be
added in later steps.

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
│   │   └── config.py
│   ├── database/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── calculation_history.py
│   ├── schemas/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   └── api/
│       ├── __init__.py
│       └── routes/
│           └── __init__.py
├── tests/
│   └── __init__.py
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

## Database

The MySQL schema is created on application startup via
`Base.metadata.create_all()`. Only one table exists at this stage:

- `calculation_history`

| column       | type           | notes                          |
|--------------|----------------|--------------------------------|
| id           | INT            | PK, auto increment             |
| expression   | VARCHAR(1024)  | NOT NULL                       |
| result       | VARCHAR(1024)  | NOT NULL, stored as text       |
| created_at   | DATETIME       | NOT NULL, server-side default  |

The `result` column is stored as text so that values can be represented in a
form that avoids avoidable floating-point display problems (for example
`"0.1 + 0.2"` style canonical forms or arbitrary-precision decimals).

## CORS

The local Vue / Vite development origins are allowed:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Health Check

`GET /health` runs a lightweight `SELECT 1` against the database. The
response reports the application name, environment, and whether the
database is reachable. Database credentials and connection details are
never exposed in the response body.
