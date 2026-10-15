"""add projects, prompt templates and sessions.project_id

Revision ID: b5e8c2f0a9d1
Revises: 9d4f2b7e1c3a
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa

revision = "b5e8c2f0a9d1"
down_revision = "9d4f2b7e1c3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prompt_templates_user_id", "prompt_templates", ["user_id"])
    op.add_column("sessions", sa.Column("project_id", sa.String(), nullable=True))
    op.create_index("ix_sessions_project_id", "sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_project_id", table_name="sessions")
    op.drop_column("sessions", "project_id")
    op.drop_index("ix_prompt_templates_user_id", table_name="prompt_templates")
    op.drop_table("prompt_templates")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
