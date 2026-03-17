"""Add circle enhancements and origin expiry tracking.

Revision ID: 004
Revises: 003
Create Date: 2026-03-13

Changes:
- Add expired_at column to relationship_origins for circle edge expiry
- Add index on relationship_origins for same_circle origin lookups
- Add index on circle_memberships for agent lookup
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add expired_at to relationship_origins
    op.add_column(
        "relationship_origins",
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Index for same_circle origin lookups (used by expire_circle_edges)
    op.create_index(
        "ix_origins_type_source",
        "relationship_origins",
        ["origin_type", "source_id"],
        unique=False,
    )

    # Index for circle membership by agent (used by list_my_circles)
    op.create_index(
        "ix_circle_memberships_agent",
        "circle_memberships",
        ["agent_id"],
        unique=False,
    )

    # Index for circle active status
    op.create_index(
        "ix_circles_active",
        "circles",
        ["is_active"],
        unique=False,
    )

    # Composite index for relationship edge lookups
    op.create_index(
        "ix_edges_from_to",
        "relationship_edges",
        ["from_agent_id", "to_agent_id"],
        unique=True,
    )

    # Index for task inbox queries
    op.create_index(
        "ix_tasks_to_agent_status",
        "tasks",
        ["to_agent_id", "status"],
        unique=False,
    )

    # Index for agent search by visibility
    op.create_index(
        "ix_agents_visibility_status",
        "agents",
        ["visibility_scope", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agents_visibility_status", table_name="agents")
    op.drop_index("ix_tasks_to_agent_status", table_name="tasks")
    op.drop_index("ix_edges_from_to", table_name="relationship_edges")
    op.drop_index("ix_circles_active", table_name="circles")
    op.drop_index("ix_circle_memberships_agent", table_name="circle_memberships")
    op.drop_index("ix_origins_type_source", table_name="relationship_origins")
    op.drop_column("relationship_origins", "expired_at")
