"""add_regulatory_documents_and_versions

Revision ID: e9bb67c3fcff
Revises: 745e36504da5
Create Date: 2026-10-07 22:25:54.887248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9bb67c3fcff'
down_revision: Union[str, Sequence[str], None] = '745e36504da5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('regulatory_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('source', sa.String(length=512), nullable=True),
        sa.Column('jurisdiction', sa.String(length=128), nullable=True),
        sa.Column('document_type', sa.String(length=128), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regulatory_documents_organization_id'), 'regulatory_documents', ['organization_id'], unique=False)
    op.create_index(op.f('ix_regulatory_documents_title'), 'regulatory_documents', ['title'], unique=False)

    op.create_table('regulatory_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('file_reference', sa.String(length=1024), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['regulatory_documents.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regulatory_versions_document_id'), 'regulatory_versions', ['document_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_regulatory_versions_document_id'), table_name='regulatory_versions')
    op.drop_table('regulatory_versions')
    op.drop_index(op.f('ix_regulatory_documents_title'), table_name='regulatory_documents')
    op.drop_index(op.f('ix_regulatory_documents_organization_id'), table_name='regulatory_documents')
    op.drop_table('regulatory_documents')
