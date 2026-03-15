# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""
Initial Murphy System database schema.

Creates core tables: sessions, living_documents, execution_records,
audit_trail, hitl_interventions.

Revision ID: 001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(128), primary_key=True),
        sa.Column("data", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "living_documents",
        sa.Column("doc_id", sa.String(128), primary_key=True),
        sa.Column("state", sa.String(32), default="DRAFT"),
        sa.Column("confidence", sa.Float, default=0.0),
        sa.Column("content", sa.Text, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "execution_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(128), sa.ForeignKey("sessions.session_id"), nullable=True),
        sa.Column("task_type", sa.String(64), default="general"),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_trail",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), default="system"),
        sa.Column("payload", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "hitl_interventions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(32), default="pending"),
        sa.Column("response", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("hitl_interventions")
    op.drop_table("audit_trail")
    op.drop_table("execution_records")
    op.drop_table("living_documents")
    op.drop_table("sessions")
