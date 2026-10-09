"""Persist proposed evidence/test assessments separately from human decisions."""
from alembic import op
import sqlalchemy as sa
revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('evidence', sa.Column('validation_result', sa.Text(), nullable=True))
    op.add_column('control_tests', sa.Column('proposed_result', sa.Text(), nullable=True))
    op.add_column('control_tests', sa.Column('review_status', sa.String(32), nullable=False, server_default='manual'))


def downgrade():
    op.drop_column('control_tests', 'review_status')
    op.drop_column('control_tests', 'proposed_result')
    op.drop_column('evidence', 'validation_result')
