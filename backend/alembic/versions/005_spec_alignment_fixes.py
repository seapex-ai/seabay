"""Spec alignment fixes — model field additions.

Revision ID: 005
Revises: 004
Create Date: 2026-03-14

Changes:
- Add visibility and invite_link_ttl to circles
- Add invited_by and joined_at to circle_memberships
- Add expires_at to circle_join_requests
- Add issued_for_agent_id to human_confirm_sessions
- Fix max_delivery_attempts default from 3 to 4
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # circles: add visibility and invite_link_ttl
    op.add_column(
        "circles",
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
    )
    op.add_column(
        "circles",
        sa.Column("invite_link_ttl", sa.Integer(), nullable=True, server_default="604800"),
    )

    # circle_memberships: add invited_by and joined_at
    op.add_column(
        "circle_memberships",
        sa.Column("invited_by", sa.String(32), nullable=True),
    )
    op.add_column(
        "circle_memberships",
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )

    # circle_join_requests: add expires_at
    op.add_column(
        "circle_join_requests",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # human_confirm_sessions: add issued_for_agent_id
    op.add_column(
        "human_confirm_sessions",
        sa.Column("issued_for_agent_id", sa.String(32), nullable=True),
    )

    # Fix max_delivery_attempts default (3 → 4, spec: 1 initial + 3 retries)
    op.alter_column(
        "tasks",
        "max_delivery_attempts",
        server_default="4",
    )


def downgrade() -> None:
    op.alter_column("tasks", "max_delivery_attempts", server_default="3")
    op.drop_column("human_confirm_sessions", "issued_for_agent_id")
    op.drop_column("circle_join_requests", "expires_at")
    op.drop_column("circle_memberships", "joined_at")
    op.drop_column("circle_memberships", "invited_by")
    op.drop_column("circles", "invite_link_ttl")
    op.drop_column("circles", "visibility")
