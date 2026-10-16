"""google sign-in: users.google_sub, nullable password_hash

Revision ID: d2a7f4c8e1b6
Revises: b5e8c2f0a9d1
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa

revision = "d2a7f4c8e1b6"
down_revision = "b5e8c2f0a9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(), nullable=True))
    op.create_index("ix_users_google_sub", "users", ["google_sub"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Google-only users have no password; they can't survive the NOT NULL constraint.
    op.execute("DELETE FROM users WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_users_google_sub", table_name="users")
    op.drop_column("users", "google_sub")
