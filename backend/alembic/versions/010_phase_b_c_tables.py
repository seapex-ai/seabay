"""Phase B + C tables: publications, task_messages, organizations.

Revision ID: 010
Revises: 009
Create Date: 2026-03-24

Changes:
- Create publications table (Phase B)
- Create task_messages table (Phase B)
- Create organizations table (Phase C)
- Create org_memberships table (Phase C)
- Create org_policies table (Phase C)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Phase B: publications ──
    op.create_table(
        "publications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("publication_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("structured_data", postgresql.JSONB(), server_default="{}"),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("price_summary", sa.String(128), nullable=True),
        sa.Column("availability_summary", sa.String(128), nullable=True),
        sa.Column("location_city", sa.String(100), nullable=True),
        sa.Column("location_country", sa.String(2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("visibility_scope", sa.String(20), nullable=False, server_default="public"),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_pub_agent", "publications", ["agent_id"])
    op.create_index("idx_pub_type", "publications", ["publication_type"])
    op.create_index("idx_pub_status", "publications", ["status"])
    op.create_index("idx_pub_visibility", "publications", ["visibility_scope"])

    # ── Phase B: task_messages ──
    op.create_table(
        "task_messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("from_agent_id", sa.String(32), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_data", postgresql.JSONB(), nullable=True),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_tmsg_task", "task_messages", ["task_id"])
    op.create_index("idx_tmsg_from", "task_messages", ["from_agent_id"])

    # ── Phase C: organizations ──
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_agent_id", sa.String(32), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("verification_level", sa.String(30), nullable=False, server_default="none"),
        sa.Column("domain", sa.String(200), nullable=True),
        sa.Column("default_contact_policy", sa.String(30), nullable=False, server_default="known_direct"),
        sa.Column("default_visibility", sa.String(20), nullable=False, server_default="network_only"),
        sa.Column("allowed_agent_types", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("max_members", sa.Integer(), server_default="100"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_org_slug", "organizations", ["slug"])
    op.create_index("idx_org_owner", "organizations", ["owner_agent_id"])

    # ── Phase C: org_memberships ──
    op.create_table(
        "org_memberships",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("org_id", sa.String(32), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_orgmem_org", "org_memberships", ["org_id"])
    op.create_index("idx_orgmem_agent", "org_memberships", ["agent_id"])

    # ── Phase C: org_policies ──
    op.create_table(
        "org_policies",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("org_id", sa.String(32), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("policy_type", sa.String(30), nullable=False),
        sa.Column("policy_key", sa.String(50), nullable=False),
        sa.Column("policy_value", sa.Text(), nullable=False),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_orgpol_org", "org_policies", ["org_id"])


def downgrade() -> None:
    op.drop_table("org_policies")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
    op.drop_table("task_messages")
    op.drop_table("publications")
