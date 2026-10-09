"""add_pgvector_embedding

Revision ID: a1b2c3d4e5f6
Revises: c1f543e0d892
Create Date: 2026-10-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c1f543e0d892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    op.add_column(
        'regulatory_versions',
        sa.Column('embedding', Vector(1536), nullable=True)
    )

    op.add_column(
        'regulatory_versions',
        sa.Column('job_id', sa.String(64), nullable=True)
    )

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_regulatory_versions_embedding
        ON regulatory_versions
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_regulatory_versions_embedding;')
    op.drop_column('regulatory_versions', 'job_id')
    op.drop_column('regulatory_versions', 'embedding')
    op.execute('DROP EXTENSION IF EXISTS vector;')