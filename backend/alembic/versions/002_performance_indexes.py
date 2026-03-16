"""Add performance indexes for query optimization.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tasks: inbox query (to_agent_id + status), delivery worker (status + next_delivery_at)
    op.create_index("idx_tasks_to_agent_status", "tasks", ["to_agent_id", "status"])
    op.create_index("idx_tasks_from_agent", "tasks", ["from_agent_id"])
    op.create_index("idx_tasks_status_delivery", "tasks", ["status", "next_delivery_at"])
    op.create_index("idx_tasks_idempotency", "tasks", ["idempotency_key"])
    op.create_index("idx_tasks_expires", "tasks", ["expires_at"])

    # Relationships: edge lookup (from + to), strength queries
    op.create_index("idx_edges_from_to", "relationship_edges", ["from_agent_id", "to_agent_id"])
    op.create_index("idx_edges_from_agent", "relationship_edges", ["from_agent_id"])
    op.create_index("idx_edges_to_agent", "relationship_edges", ["to_agent_id"])

    # Relationship origins: edge_id lookup
    op.create_index("idx_origins_edge", "relationship_origins", ["edge_id"])

    # Circles: membership lookups
    op.create_index("idx_memberships_circle", "circle_memberships", ["circle_id"])
    op.create_index("idx_memberships_agent", "circle_memberships", ["agent_id"])
    op.create_index("idx_join_requests_circle", "circle_join_requests", ["circle_id", "status"])

    # Intents: from_agent lookup, expiry
    op.create_index("idx_intents_from_agent", "intents", ["from_agent_id"])
    op.create_index("idx_intents_status_expires", "intents", ["status", "expires_at"])

    # Introductions: target lookup, expiry
    op.create_index("idx_introductions_target_a", "introductions", ["target_a_agent_id"])
    op.create_index("idx_introductions_target_b", "introductions", ["target_b_agent_id"])
    op.create_index("idx_introductions_expires", "introductions", ["expires_at"])

    # Reports: reported agent, reporter
    op.create_index("idx_reports_reported", "reports", ["reported_agent_id", "status"])
    op.create_index("idx_reports_reporter", "reports", ["reporter_agent_id"])

    # Verifications: agent_id + method
    op.create_index("idx_verifications_agent", "verifications", ["agent_id", "method"])

    # Interactions: agent pair
    op.create_index("idx_interactions_from_to", "interactions", ["from_agent_id", "to_agent_id"])

    # Agents: status (for status_decay worker), last_seen
    op.create_index("idx_agents_status", "agents", ["status"])
    op.create_index("idx_agents_last_seen", "agents", ["last_seen_at"])

    # Profile: skills GIN index for overlap queries
    op.execute("CREATE INDEX idx_profiles_skills ON profiles USING GIN (skills)")
    op.execute("CREATE INDEX idx_profiles_languages ON profiles USING GIN (languages)")


def downgrade() -> None:
    op.drop_index("idx_profiles_languages")
    op.drop_index("idx_profiles_skills")
    op.drop_index("idx_agents_last_seen")
    op.drop_index("idx_agents_status")
    op.drop_index("idx_interactions_from_to")
    op.drop_index("idx_verifications_agent")
    op.drop_index("idx_reports_reporter")
    op.drop_index("idx_reports_reported")
    op.drop_index("idx_introductions_expires")
    op.drop_index("idx_introductions_target_b")
    op.drop_index("idx_introductions_target_a")
    op.drop_index("idx_intents_status_expires")
    op.drop_index("idx_intents_from_agent")
    op.drop_index("idx_join_requests_circle")
    op.drop_index("idx_memberships_agent")
    op.drop_index("idx_memberships_circle")
    op.drop_index("idx_origins_edge")
    op.drop_index("idx_edges_to_agent")
    op.drop_index("idx_edges_from_agent")
    op.drop_index("idx_edges_from_to")
    op.drop_index("idx_tasks_expires")
    op.drop_index("idx_tasks_idempotency")
    op.drop_index("idx_tasks_status_delivery")
    op.drop_index("idx_tasks_from_agent")
    op.drop_index("idx_tasks_to_agent_status")
