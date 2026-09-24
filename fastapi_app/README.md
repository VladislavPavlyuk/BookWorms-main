# FastAPI strangler (SQLAlchemy Core + Pydantic)

Parallel process next to Django. Same Postgres. Django keeps owning `mainApp_*`
schema; Alembic only touches `fastapi_*`.

## Setup

```bash
pip install -r requirements-fastapi.txt
# same POSTGRES_* as Django (.env)
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=5432
export POSTGRES_DB=bookworms POSTGRES_USER=bookworms POSTGRES_PASSWORD=...
```

## Run (local)

```bash
pip install -r requirements-fastapi.txt
uvicorn fastapi_app.main:app --reload --port 8001
```

## Run (QNAP — no host pip)

Host shell has no Python. Use Docker:

```bash
cd /share/Container/BookWorms-main
docker compose -f docker-compose.qnap.yml up -d --build fastapi
# or full stack: docker compose -f docker-compose.qnap.yml up -d --build
```

- direct: `http://<nas>:18089/health`
- via nginx: `http://<nas>:18088/fastapi/health`
- shelves: `/v1/shelves/available-owned`, `/v1/shelves/physical-presence`
- OpenAPI: `/docs` (or `/fastapi/docs` via nginx)

## Alembic (fastapi_* only)

```bash
cd fastapi_app
alembic upgrade head
```

`include_object` filters out Django tables — do not autogenerate against `mainApp_*`.

## Boundary

| Concern | Owner |
|---------|--------|
| Web UI, admin, auth sessions, writes (exchange mutations) | Django |
| Read slice: shelf browse queries | FastAPI (this package) |
| Table DDL for books/shelves/users | Django migrations |
| `fastapi_schema_meta` | Alembic |

## Auth (JWT)

- `POST /auth/login` `{username, password}` → `{access, refresh, user}`
- `POST /auth/refresh` `{refresh}` → new pair
- `POST /auth/register` — only when `SKIP_EMAIL_ACTIVATION=1` (else use Django `/api/auth/register/`)
- Shelf routes require `Authorization: Bearer <access>` (SimpleJWT-compatible, `DJANGO_SECRET_KEY`)
- TLS at edge; nginx forwards `Authorization` on `/fastapi/`

## Tests (repo / live DB)

```bash
docker compose -f docker-compose.test.yml up -d
# or on QNAP:
sh deploy/qnap/run-repo-tests.sh fastapi
```

Naming: `test_<method>_<when…>_<returns…>`; `actualResult` / `expectedResult`; one assert.
Higher layers mock the repo — do not hit DB there.
