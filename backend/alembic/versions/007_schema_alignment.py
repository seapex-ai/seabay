"""Schema alignment — foreign keys, indexes, unique constraints, pgcrypto, audit_logs table.

Revision ID: 007
Revises: 006
Create Date: 2026-03-20

Changes:
- Enable pgcrypto extension
- Create audit_logs table for persistent moderation audit trail
- Add all missing foreign keys per frozen spec (schema.sql)
- Add missing indexes per spec
- Add missing unique constraints per spec
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pgcrypto extension ──
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── audit_logs table (V1.6 — replaces in-memory audit log) ──
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(32), nullable=True),
        sa.Column("details", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"])
    op.create_index("idx_audit_logs_actor", "audit_logs", ["actor_id"])
    op.create_index("idx_audit_logs_target", "audit_logs", ["target_id"])
    op.create_index("idx_audit_logs_created", "audit_logs", ["created_at"])

    # ── Foreign Keys ──

    # relationship_edges.from_agent_id → agents.id
    op.create_foreign_key(
        "fk_rel_edges_from_agent",
        "relationship_edges", "agents",
        ["from_agent_id"], ["id"],
        ondelete="CASCADE",
    )
    # relationship_edges.to_agent_id → agents.id
    op.create_foreign_key(
        "fk_rel_edges_to_agent",
        "relationship_edges", "agents",
        ["to_agent_id"], ["id"],
        ondelete="CASCADE",
    )

    # relationship_origins.edge_id → relationship_edges.id ON DELETE CASCADE
    op.create_foreign_key(
        "fk_rel_origins_edge",
        "relationship_origins", "relationship_edges",
        ["edge_id"], ["id"],
        ondelete="CASCADE",
    )

    # circles.owner_agent_id → agents.id
    op.create_foreign_key(
        "fk_circles_owner_agent",
        "circles", "agents",
        ["owner_agent_id"], ["id"],
        ondelete="CASCADE",
    )

    # circle_memberships.circle_id → circles.id ON DELETE CASCADE
    op.create_foreign_key(
        "fk_cmb_circle",
        "circle_memberships", "circles",
        ["circle_id"], ["id"],
        ondelete="CASCADE",
    )
    # circle_memberships.agent_id → agents.id ON DELETE CASCADE
    op.create_foreign_key(
        "fk_cmb_agent",
        "circle_memberships", "agents",
        ["agent_id"], ["id"],
        ondelete="CASCADE",
    )

    # circle_join_requests.circle_id → circles.id ON DELETE CASCADE
    op.create_foreign_key(
        "fk_cjr_circle",
        "circle_join_requests", "circles",
        ["circle_id"], ["id"],
        ondelete="CASCADE",
    )
    # circle_join_requests.agent_id → agents.id
    op.create_foreign_key(
        "fk_cjr_agent",
        "circle_join_requests", "agents",
        ["agent_id"], ["id"],
    )

    # introductions.introducer_agent_id → agents.id
    op.create_foreign_key(
        "fk_intro_introducer",
        "introductions", "agents",
        ["introducer_agent_id"], ["id"],
    )
    # introductions.target_a_agent_id → agents.id
    op.create_foreign_key(
        "fk_intro_target_a",
        "introductions", "agents",
        ["target_a_agent_id"], ["id"],
    )
    # introductions.target_b_agent_id → agents.id
    op.create_foreign_key(
        "fk_intro_target_b",
        "introductions", "agents",
        ["target_b_agent_id"], ["id"],
    )

    # intents.from_agent_id → agents.id
    op.create_foreign_key(
        "fk_intents_from_agent",
        "intents", "agents",
        ["from_agent_id"], ["id"],
    )

    # tasks.from_agent_id → agents.id
    op.create_foreign_key(
        "fk_tasks_from_agent",
        "tasks", "agents",
        ["from_agent_id"], ["id"],
    )
    # tasks.to_agent_id → agents.id
    op.create_foreign_key(
        "fk_tasks_to_agent",
        "tasks", "agents",
        ["to_agent_id"], ["id"],
    )
    # tasks.intent_id → intents.id
    op.create_foreign_key(
        "fk_tasks_intent",
        "tasks", "intents",
        ["intent_id"], ["id"],
    )

    # interactions.task_id → tasks.id
    op.create_foreign_key(
        "fk_ixn_task",
        "interactions", "tasks",
        ["task_id"], ["id"],
    )
    # interactions.from_agent_id → agents.id
    op.create_foreign_key(
        "fk_ixn_from_agent",
        "interactions", "agents",
        ["from_agent_id"], ["id"],
    )
    # interactions.to_agent_id → agents.id
    op.create_foreign_key(
        "fk_ixn_to_agent",
        "interactions", "agents",
        ["to_agent_id"], ["id"],
    )

    # verifications.agent_id → agents.id ON DELETE CASCADE
    op.create_foreign_key(
        "fk_vrf_agent",
        "verifications", "agents",
        ["agent_id"], ["id"],
        ondelete="CASCADE",
    )

    # reports.reporter_agent_id → agents.id
    op.create_foreign_key(
        "fk_rpt_reporter",
        "reports", "agents",
        ["reporter_agent_id"], ["id"],
    )
    # reports.reported_agent_id → agents.id
    op.create_foreign_key(
        "fk_rpt_reported",
        "reports", "agents",
        ["reported_agent_id"], ["id"],
    )

    # human_confirm_sessions.task_id → tasks.id
    op.create_foreign_key(
        "fk_hcs_task",
        "human_confirm_sessions", "tasks",
        ["task_id"], ["id"],
    )

    # ── Missing Indexes (per spec) ──

    # profiles: idx_profiles_agent, idx_profiles_location
    op.create_index("idx_profiles_agent", "profiles", ["agent_id"])
    op.create_index("idx_profiles_location", "profiles", ["location_country", "location_city"])

    # relationship_edges: idx_rel_strength
    op.create_index("idx_rel_strength", "relationship_edges", ["strength"])

    # circles: idx_circles_owner
    op.create_index("idx_circles_owner", "circles", ["owner_agent_id"])

    # intents: idx_intents_category, idx_intents_audience
    op.create_index("idx_intents_category", "intents", ["category"])
    op.create_index("idx_intents_audience", "intents", ["audience_scope"])

    # tasks: idx_tasks_risk, idx_tasks_intent
    op.create_index("idx_tasks_risk", "tasks", ["risk_level"])
    op.create_index("idx_tasks_intent", "tasks", ["intent_id"])

    # interactions: idx_ixn_task, idx_ixn_outcome
    op.create_index("idx_ixn_task", "interactions", ["task_id"])
    op.create_index("idx_ixn_outcome", "interactions", ["outcome"])

    # human_confirm_sessions: idx_hcs_task
    op.create_index("idx_hcs_task", "human_confirm_sessions", ["task_id"])

    # verifications: idx_vrf_method, idx_vrf_status
    op.create_index("idx_vrf_method", "verifications", ["method"])
    op.create_index("idx_vrf_status", "verifications", ["status"])

    # reports: idx_rpt_reason
    op.create_index("idx_rpt_reason", "reports", ["reason_code"])

    # ── Missing Unique Constraints ──

    # profile_field_visibility: UNIQUE (agent_id, field_name)
    op.create_unique_constraint(
        "uq_pfv_agent_field",
        "profile_field_visibility",
        ["agent_id", "field_name"],
    )

    # relationship_origins: UNIQUE (edge_id, origin_type, source_id)
    op.create_unique_constraint(
        "uq_origins_edge_type_source",
        "relationship_origins",
        ["edge_id", "origin_type", "source_id"],
    )


def downgrade() -> None:
    # ── Drop Unique Constraints ──
    op.drop_constraint("uq_origins_edge_type_source", "relationship_origins", type_="unique")
    op.drop_constraint("uq_pfv_agent_field", "profile_field_visibility", type_="unique")

    # ── Drop Indexes ──
    op.drop_index("idx_rpt_reason", table_name="reports")
    op.drop_index("idx_vrf_status", table_name="verifications")
    op.drop_index("idx_vrf_method", table_name="verifications")
    op.drop_index("idx_hcs_task", table_name="human_confirm_sessions")
    op.drop_index("idx_ixn_outcome", table_name="interactions")
    op.drop_index("idx_ixn_task", table_name="interactions")
    op.drop_index("idx_tasks_intent", table_name="tasks")
    op.drop_index("idx_tasks_risk", table_name="tasks")
    op.drop_index("idx_intents_audience", table_name="intents")
    op.drop_index("idx_intents_category", table_name="intents")
    op.drop_index("idx_circles_owner", table_name="circles")
    op.drop_index("idx_rel_strength", table_name="relationship_edges")
    op.drop_index("idx_profiles_location", table_name="profiles")
    op.drop_index("idx_profiles_agent", table_name="profiles")

    # ── Drop Foreign Keys ──
    op.drop_constraint("fk_hcs_task", "human_confirm_sessions", type_="foreignkey")
    op.drop_constraint("fk_rpt_reported", "reports", type_="foreignkey")
    op.drop_constraint("fk_rpt_reporter", "reports", type_="foreignkey")
    op.drop_constraint("fk_vrf_agent", "verifications", type_="foreignkey")
    op.drop_constraint("fk_ixn_to_agent", "interactions", type_="foreignkey")
    op.drop_constraint("fk_ixn_from_agent", "interactions", type_="foreignkey")
    op.drop_constraint("fk_ixn_task", "interactions", type_="foreignkey")
    op.drop_constraint("fk_tasks_intent", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_to_agent", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_from_agent", "tasks", type_="foreignkey")
    op.drop_constraint("fk_intents_from_agent", "intents", type_="foreignkey")
    op.drop_constraint("fk_intro_target_b", "introductions", type_="foreignkey")
    op.drop_constraint("fk_intro_target_a", "introductions", type_="foreignkey")
    op.drop_constraint("fk_intro_introducer", "introductions", type_="foreignkey")
    op.drop_constraint("fk_cjr_agent", "circle_join_requests", type_="foreignkey")
    op.drop_constraint("fk_cjr_circle", "circle_join_requests", type_="foreignkey")
    op.drop_constraint("fk_cmb_agent", "circle_memberships", type_="foreignkey")
    op.drop_constraint("fk_cmb_circle", "circle_memberships", type_="foreignkey")
    op.drop_constraint("fk_circles_owner_agent", "circles", type_="foreignkey")
    op.drop_constraint("fk_rel_origins_edge", "relationship_origins", type_="foreignkey")
    op.drop_constraint("fk_rel_edges_to_agent", "relationship_edges", type_="foreignkey")
    op.drop_constraint("fk_rel_edges_from_agent", "relationship_edges", type_="foreignkey")

    # ── Drop audit_logs table ──
    op.drop_index("idx_audit_logs_created", table_name="audit_logs")
    op.drop_index("idx_audit_logs_target", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")
