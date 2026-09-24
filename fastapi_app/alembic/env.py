"""Alembic env — only mutate fastapi_* tables."""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# repo root on path so `fastapi_app` imports work when cwd is fastapi_app/
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi_app.config import get_settings  # noqa: E402
from fastapi_app.tables import metadata  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Only FastAPI-owned table(s) for autogenerate target
target_metadata = metadata


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        return name is not None and name.startswith("fastapi_")
    return True


def run_migrations_offline() -> None:
    url = get_settings().sqlalchemy_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_name=lambda name, type_, parent_names: (
            type_ != "table" or (name or "").startswith("fastapi_")
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_settings().sqlalchemy_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
