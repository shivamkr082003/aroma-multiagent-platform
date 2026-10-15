"""add sources to messages

Revision ID: 9d4f2b7e1c3a
Revises: 7c3e9a1d4b2f
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa

revision = "9d4f2b7e1c3a"
down_revision = "7c3e9a1d4b2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("sources", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "sources")
