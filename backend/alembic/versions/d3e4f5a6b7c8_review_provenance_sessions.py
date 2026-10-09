"""Preserve pages, applicability and revocation; make test execution idempotent.

Revision ID: d3e4f5a6b7c8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d3e4f5a6b7c8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("regulatory_versions", sa.Column("source_pages", sa.Text(), nullable=True))
    op.add_column("regulatory_obligations", sa.Column("applicability", sa.String(32), nullable=False, server_default="uncertain"))
    op.add_column("control_tests", sa.Column("execution_id", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_control_tests_execution_id", "control_tests", ["execution_id"])
    op.create_table("revoked_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_revoked_sessions_user_id", "revoked_sessions", ["user_id"])
    op.create_index("ix_revoked_sessions_expires_at", "revoked_sessions", ["expires_at"])


def downgrade():
    op.drop_table("revoked_sessions")
    op.drop_constraint("uq_control_tests_execution_id", "control_tests", type_="unique")
    op.drop_column("control_tests", "execution_id")
    op.drop_column("regulatory_obligations", "applicability")
    op.drop_column("regulatory_versions", "source_pages")
