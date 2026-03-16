"""Add api_key_prefix column with index for O(1) auth lookup.

Revision ID: 006
Revises: 005
Create Date: 2026-03-16

Changes:
- Add api_key_prefix (String(16), indexed) to agents table
- Enables prefix-based lookup instead of O(n) bcrypt scan
- Existing agents will have prefix backfilled on first auth
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("api_key_prefix", sa.String(16), nullable=True),
    )
    op.create_index("ix_agents_api_key_prefix", "agents", ["api_key_prefix"])


def downgrade() -> None:
    op.drop_index("ix_agents_api_key_prefix", table_name="agents")
    op.drop_column("agents", "api_key_prefix")
