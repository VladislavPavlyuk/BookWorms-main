from __future__ import annotations

from fastapi import FastAPI

from .auth.router import router as auth_router
from .routers import health, shelves

app = FastAPI(
    title="BookWorms Exchange API (FastAPI)",
    version="0.1.0",
    description=(
        "Strangler slice: SQLAlchemy Core + Pydantic + JWT (SimpleJWT-compatible). "
        "Schema for mainApp_* stays in Django; Alembic only owns fastapi_*."
    ),
)

app.include_router(health.router)
app.include_router(auth_router)
app.include_router(shelves.router, prefix="/v1")


@app.get("/")
def root():
    return {"service": "bookworms-fastapi", "docs": "/docs"}
