"""Add publication_ref to tasks and audience_preference to intents.

Revision ID: 011
Revises: 010
Create Date: 2026-03-24

Changes:
- Add publication_ref to tasks table
- Add audience_preference to intents table
"""

import sqlalchemy as sa

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("publication_ref", sa.String(32), nullable=True))
    op.add_column("intents", sa.Column("audience_preference", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("intents", "audience_preference")
    op.drop_column("tasks", "publication_ref")
