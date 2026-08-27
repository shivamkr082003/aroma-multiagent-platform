"""add mcp server configurations

Revision ID: 1b15b0ed2a7c
Revises: 65f4f736e748
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "1b15b0ed2a7c"
down_revision = "65f4f736e748"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some existing Aroma installations created this table through
    # create_tables.py before this Alembic revision was introduced.
    # In that case, keep the existing data/table and advance Alembic's
    # version rather than failing with DuplicateTable.
    if inspect(op.get_bind()).has_table("mcp_servers"):
        return

    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("transport", sa.String(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("command", sa.String(), nullable=True),
        sa.Column("args", sa.JSON(), nullable=True),
        sa.Column("env", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_mcp_servers_user_name"),
    )
    op.create_index("ix_mcp_servers_user_id", "mcp_servers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_servers_user_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
