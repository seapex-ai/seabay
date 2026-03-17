"""Initial schema for Seabay V1.5 — 17 tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. agents
    op.create_table(
        "agents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("agent_type", sa.String(20), nullable=False, server_default="personal"),
        sa.Column("owner_type", sa.String(20), nullable=False, server_default="individual"),
        sa.Column("runtime", sa.String(50)),
        sa.Column("framework", sa.String(50)),
        sa.Column("endpoint", sa.String(500)),
        sa.Column("namespace", sa.String(200)),
        sa.Column("api_key_hash", sa.String(128), nullable=False),
        sa.Column("verification_level", sa.String(30), nullable=False, server_default="none"),
        sa.Column("public_key", sa.Text()),
        sa.Column("signature_alg", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, server_default="online"),
        sa.Column("contact_policy", sa.String(30), nullable=False, server_default="known_direct"),
        sa.Column("introduction_policy", sa.String(30), nullable=False, server_default="confirm_required"),
        sa.Column("visibility_scope", sa.String(20), nullable=False, server_default="network_only"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("key_rotated_at", sa.DateTime(timezone=True)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("passport_display_name", sa.String(128)),
        sa.Column("passport_tagline", sa.String(256)),
        sa.Column("passport_avatar_url", sa.Text()),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_agents_slug", "agents", ["slug"])
    op.create_index("idx_agents_type", "agents", ["agent_type"])
    op.create_index("idx_agents_region", "agents", ["region"])

    # 2. profiles
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.id"), nullable=False, unique=True),
        sa.Column("bio", sa.Text()),
        sa.Column("skills", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("risk_capabilities", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("interests", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("languages", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("location_city", sa.String(100)),
        sa.Column("location_country", sa.String(2)),
        sa.Column("timezone", sa.String(40)),
        sa.Column("pricing", sa.String(50), server_default="free"),
        sa.Column("profile_theme", sa.String(50)),
        sa.Column("can_offer", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("looking_for", postgresql.ARRAY(sa.Text()), server_default="{}"),
        sa.Column("pricing_hint", sa.String(128)),
        sa.Column("homepage_url", sa.Text()),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 3. profile_field_visibility
    op.create_table(
        "profile_field_visibility",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="network_only"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 4. relationship_edges
    op.create_table(
        "relationship_edges",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("from_agent_id", sa.String(32), nullable=False),
        sa.Column("to_agent_id", sa.String(32), nullable=False),
        sa.Column("strength", sa.String(20), nullable=False, server_default="new"),
        sa.Column("starred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_direct_task", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_introduce", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blocked_at", sa.DateTime(timezone=True)),
        sa.Column("last_rating", sa.SmallInteger()),
        sa.Column("tags", postgresql.JSONB(), server_default="[]"),
        sa.Column("total_interactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_interactions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("from_agent_id", "to_agent_id"),
    )

    # 5. relationship_origins
    op.create_table(
        "relationship_origins",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("edge_id", sa.String(32), nullable=False),
        sa.Column("origin_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("source_id", sa.String(32)),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 6. circles
    op.create_table(
        "circles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner_agent_id", sa.String(32), nullable=False),
        sa.Column("join_mode", sa.String(16), nullable=False, server_default="invite_only"),
        sa.Column("contact_mode", sa.String(16), nullable=False, server_default="request_only"),
        sa.Column("max_members", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("invite_link_token", sa.String(64)),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 7. circle_memberships
    op.create_table(
        "circle_memberships",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("circle_id", sa.String(32), nullable=False),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("role", sa.String(8), nullable=False, server_default="member"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 8. circle_join_requests
    op.create_table(
        "circle_join_requests",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("circle_id", sa.String(32), nullable=False),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(32)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 9. introductions
    op.create_table(
        "introductions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("introducer_agent_id", sa.String(32), nullable=False),
        sa.Column("target_a_agent_id", sa.String(32), nullable=False),
        sa.Column("target_b_agent_id", sa.String(32), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("a_responded_at", sa.DateTime(timezone=True)),
        sa.Column("b_responded_at", sa.DateTime(timezone=True)),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default="259200"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 10. intents
    op.create_table(
        "intents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("from_agent_id", sa.String(32), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("structured_requirements", postgresql.JSONB(), server_default="{}"),
        sa.Column("audience_scope", sa.String(64), nullable=False, server_default="public"),
        sa.Column("status", sa.String(12), nullable=False, server_default="active"),
        sa.Column("max_matches", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("ttl_hours", sa.Integer(), nullable=False, server_default="72"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 11. tasks
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("from_agent_id", sa.String(32), nullable=False),
        sa.Column("to_agent_id", sa.String(32), nullable=False),
        sa.Column("intent_id", sa.String(32)),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("payload_ref", sa.String(500)),
        sa.Column("payload_inline", postgresql.JSONB()),
        sa.Column("risk_level", sa.String(4), nullable=False, server_default="R0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_delivery"),
        sa.Column("requires_human_confirm", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("human_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("human_confirm_timeout_seconds", sa.Integer(), server_default="3600"),
        sa.Column("human_confirm_channel", sa.String(20)),
        sa.Column("human_confirm_token", sa.String(128)),
        sa.Column("human_confirm_deadline", sa.DateTime(timezone=True)),
        sa.Column("delivery_attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("max_delivery_attempts", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("next_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False, server_default="259200"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
    )

    # 12. human_confirm_sessions
    op.create_table(
        "human_confirm_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32), nullable=False),
        sa.Column("token", sa.String(128), unique=True, nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
    )

    # 13. interactions
    op.create_table(
        "interactions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("task_id", sa.String(32), nullable=False),
        sa.Column("from_agent_id", sa.String(32), nullable=False),
        sa.Column("to_agent_id", sa.String(32), nullable=False),
        sa.Column("intent", sa.String(100)),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("rating_by_from", sa.SmallInteger()),
        sa.Column("rating_by_to", sa.SmallInteger()),
        sa.Column("report_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 14. verifications
    op.create_table(
        "verifications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("identifier", sa.String(256)),
        sa.Column("verification_code", sa.String(64)),
        sa.Column("code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 15. reports
    op.create_table(
        "reports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("reported_agent_id", sa.String(32), nullable=False),
        sa.Column("reporter_agent_id", sa.String(32), nullable=False),
        sa.Column("task_id", sa.String(32)),
        sa.Column("reason_code", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("reporter_verification_level", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(100)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 16. rate_limit_budgets
    op.create_table(
        "rate_limit_budgets",
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("budget_type", sa.String(30), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_allowed", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("agent_id", "budget_type", "window_start"),
    )

    # 17. dlp_scan_log
    op.create_table(
        "dlp_scan_log",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.String(32), nullable=False),
        sa.Column("pattern_matched", sa.String(50), nullable=False),
        sa.Column("action_taken", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_dlp_entity", "dlp_scan_log", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("dlp_scan_log")
    op.drop_table("rate_limit_budgets")
    op.drop_table("reports")
    op.drop_table("verifications")
    op.drop_table("interactions")
    op.drop_table("human_confirm_sessions")
    op.drop_table("tasks")
    op.drop_table("intents")
    op.drop_table("introductions")
    op.drop_table("circle_join_requests")
    op.drop_table("circle_memberships")
    op.drop_table("circles")
    op.drop_table("relationship_origins")
    op.drop_table("relationship_edges")
    op.drop_table("profile_field_visibility")
    op.drop_table("profiles")
    op.drop_table("agents")
