"""fastapi schema meta marker

Revision ID: 0001_fastapi_meta
Revises:
Create Date: 2026-09-24

Django owns mainApp_*. This revision only creates a FastAPI-owned marker table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_fastapi_meta"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fastapi_schema_meta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("note", sa.Text(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO fastapi_schema_meta (id, note) "
            "VALUES (1, 'FastAPI strangler present; Django owns mainApp_*')"
        )
    )


def downgrade() -> None:
    op.drop_table("fastapi_schema_meta")
