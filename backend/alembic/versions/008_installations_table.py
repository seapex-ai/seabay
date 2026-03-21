"""Create installations table for MCP host connections.

Revision ID: 008
Revises: 007
Create Date: 2026-03-20

Changes:
- Create installations table to track MCP host (Claude, ChatGPT, etc.)
  bindings to Seabay agent identities (linked or proxy).
- Add indexes on host_type and linked_agent_id for lookup performance.
- See Remote MCP Server v1.0 spec section 4.2.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("host_type", sa.String(20), nullable=False),
        sa.Column(
            "linked_agent_id",
            sa.String(32),
            sa.ForeignKey("agents.id"),
            nullable=True,
        ),
        sa.Column(
            "proxy_agent_id",
            sa.String(32),
            sa.ForeignKey("agents.id"),
            nullable=True,
        ),
        sa.Column("oauth_subject", sa.String(256), nullable=True),
        sa.Column(
            "granted_scopes",
            postgresql.ARRAY(sa.Text),
            server_default="{}",
        ),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index("idx_installations_host", "installations", ["host_type"])
    op.create_index("idx_installations_agent", "installations", ["linked_agent_id"])


def downgrade() -> None:
    op.drop_index("idx_installations_agent", table_name="installations")
    op.drop_index("idx_installations_host", table_name="installations")
    op.drop_table("installations")
