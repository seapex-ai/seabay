"""Schema changes from 2026-03-23 audit report.

Revision ID: 009
Revises: 008
Create Date: 2026-03-23

Changes:
- Add owner_id to agents table
- Add conversation_ref, thread_ref to tasks table
- Add target_pools, budget_range, trust_requirement, match_target_type, request_form to intents table
- Extend agent_type CHECK to include proxy, worker, org
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agents: add owner_id ──
    op.add_column("agents", sa.Column("owner_id", sa.String(64), nullable=True))

    # ── tasks: add conversation_ref, thread_ref ──
    op.add_column("tasks", sa.Column("conversation_ref", sa.String(128), nullable=True))
    op.add_column("tasks", sa.Column("thread_ref", sa.String(128), nullable=True))

    # ── intents: add extension fields ──
    op.add_column("intents", sa.Column("target_pools", postgresql.ARRAY(sa.Text()), server_default="{}"))
    op.add_column("intents", sa.Column("budget_range", sa.String(64), nullable=True))
    op.add_column("intents", sa.Column("trust_requirement", sa.String(20), nullable=True))
    op.add_column("intents", sa.Column("match_target_type", sa.String(20), nullable=True))
    op.add_column("intents", sa.Column("request_form", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("intents", "request_form")
    op.drop_column("intents", "match_target_type")
    op.drop_column("intents", "trust_requirement")
    op.drop_column("intents", "budget_range")
    op.drop_column("intents", "target_pools")
    op.drop_column("tasks", "thread_ref")
    op.drop_column("tasks", "conversation_ref")
    op.drop_column("agents", "owner_id")
