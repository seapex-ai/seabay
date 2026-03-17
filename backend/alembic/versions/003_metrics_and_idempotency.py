"""003: Add metrics, passport receipts, and idempotency tables.

Revision ID: 003
Revises: 002
Create Date: 2026-03-13

Adds:
- trust_metrics_daily: Daily trust score snapshots
- popularity_metrics_daily: Daily popularity snapshots
- passport_lite_receipts: Trust portability receipts
- idempotency_records: Request deduplication
"""

import sqlalchemy as sa

from alembic import op

revision = "003"
down_revision = "002"


def upgrade() -> None:
    # ── trust_metrics_daily ──
    op.create_table(
        "trust_metrics_daily",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("trust_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("verification_weight", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_rate_7d", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("report_rate_30d", sa.Float, nullable=False, server_default="0"),
        sa.Column("human_confirm_success_rate", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("cancel_expire_rate_30d", sa.Float, nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Float, nullable=False, server_default="0"),
        sa.Column("total_interactions_7d", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_interactions_30d", sa.Integer, nullable=False, server_default="0"),
        sa.Column("report_count_30d", sa.Integer, nullable=False, server_default="0"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trust_metrics_agent_date", "trust_metrics_daily", ["agent_id", "date"], unique=True)

    # ── popularity_metrics_daily ──
    op.create_table(
        "popularity_metrics_daily",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("task_received_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("task_received_7d", sa.Integer, nullable=False, server_default="0"),
        sa.Column("profile_views_7d", sa.Integer, nullable=False, server_default="0"),
        sa.Column("search_appearances_7d", sa.Integer, nullable=False, server_default="0"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pop_metrics_agent_date", "popularity_metrics_daily", ["agent_id", "date"], unique=True)

    # ── passport_lite_receipts ──
    op.create_table(
        "passport_lite_receipts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("receipt_type", sa.String(30), nullable=False),
        sa.Column("issuer", sa.String(100), nullable=False, server_default="seabay"),
        sa.Column("subject_display_name", sa.String(200), nullable=False),
        sa.Column("trust_score_at_issue", sa.Float, nullable=False, server_default="0"),
        sa.Column("verification_level_at_issue", sa.String(30), nullable=False, server_default="none"),
        sa.Column("interaction_count_at_issue", sa.Integer, nullable=False, server_default="0"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("signature", sa.String(512)),
        sa.Column("signature_alg", sa.String(20), nullable=False, server_default="hmac-sha256"),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_passport_agent", "passport_lite_receipts", ["agent_id"])

    # ── idempotency_records ──
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("request_path", sa.String(255), nullable=False),
        sa.Column("request_method", sa.String(10), nullable=False),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("response_body_hash", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("region", sa.String(10), nullable=False, server_default="intl"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_idempotency_expires", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("passport_lite_receipts")
    op.drop_table("popularity_metrics_daily")
    op.drop_table("trust_metrics_daily")
