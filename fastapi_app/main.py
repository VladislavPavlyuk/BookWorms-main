from __future__ import annotations

from fastapi import FastAPI

from .routers import health, shelves

app = FastAPI(
    title="BookWorms Exchange API (FastAPI)",
    version="0.1.0",
    description=(
        "Strangler slice: SQLAlchemy Core + Pydantic. "
        "Schema for mainApp_* stays in Django; Alembic only owns fastapi_*."
    ),
)

app.include_router(health.router)
app.include_router(shelves.router, prefix="/v1")


@app.get("/")
def root():
    return {"service": "bookworms-fastapi", "docs": "/docs"}
