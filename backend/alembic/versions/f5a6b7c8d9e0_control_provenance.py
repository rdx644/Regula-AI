"""Persist extracted control provenance and human evidence review rationale."""
from alembic import op
import sqlalchemy as sa

revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('controls', sa.Column('source_page', sa.String(32)))
    op.add_column('controls', sa.Column('source_section', sa.String(256)))
    op.add_column('controls', sa.Column('source_text_snippet', sa.Text()))
    op.add_column('evidence', sa.Column('review_notes', sa.Text()))


def downgrade():
    op.drop_column('evidence', 'review_notes')
    op.drop_column('controls', 'source_text_snippet')
    op.drop_column('controls', 'source_section')
    op.drop_column('controls', 'source_page')
