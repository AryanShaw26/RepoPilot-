"""Add pgvector extension and embedding column to code_chunks

Revision ID: 0002_pgvector
Revises: 0001_init
Create Date: 2026-11-15 09:21:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.core.config import settings
from app.core.logging import logger

revision: str = '0002_pgvector'
down_revision: Union[str, None] = '0001_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dim = settings.EMBEDDING_DIM
    op.execute(
        f"""
        DO $migration$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS vector;
            ALTER TABLE code_chunks
                ADD COLUMN IF NOT EXISTS embedding vector({dim});
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON code_chunks USING hnsw (embedding vector_cosine_ops);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'pgvector unavailable; semantic search is disabled';
        END
        $migration$;
        """
    )
    logger.info("pgvector migration attempted; semantic search is optional.")


def downgrade() -> None:
    try:
        op.execute("DROP INDEX IF EXISTS idx_chunks_embedding;")
        op.execute("ALTER TABLE code_chunks DROP COLUMN IF EXISTS embedding;")
    except Exception:
        pass
