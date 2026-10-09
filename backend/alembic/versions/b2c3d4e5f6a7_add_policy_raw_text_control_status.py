"""add_policy_raw_text_control_status

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('policies', sa.Column('raw_text', sa.Text(), nullable=True))
    op.execute("ALTER TABLE policies ALTER COLUMN status SET DEFAULT 'active';")

    op.execute("ALTER TABLE controls ALTER COLUMN status SET DEFAULT 'pending_review';")


def downgrade() -> None:
    op.drop_column('policies', 'raw_text')
    op.execute("ALTER TABLE policies ALTER COLUMN status SET DEFAULT 'active';")
    op.execute("ALTER TABLE controls ALTER COLUMN status SET DEFAULT 'active';")