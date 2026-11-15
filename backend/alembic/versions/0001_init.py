"""Initial database schema

Revision ID: 0001_init
Revises:
Create Date: 2026-11-15 09:20:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_init'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')

    # 1. sessions
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 2. repositories
    op.create_table(
        'repositories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('owner', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('branch', sa.Text(), nullable=False),
        sa.Column('commit_sha', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('stars', sa.Integer(), nullable=True),
        sa.Column('license', sa.Text(), nullable=True),
        sa.Column('topics', postgresql.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('size_kb', sa.Integer(), nullable=True),
        sa.Column('languages', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('frameworks', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('entry_points', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('readme_excerpt', sa.Text(), nullable=True),
        sa.Column('architecture_summary', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('snapshot_path', sa.Text(), nullable=True),
        sa.Column('snapshot_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('pending','processing','ready','failed')"),
        sa.UniqueConstraint('session_id', 'owner', 'name', 'commit_sha', name='uq_repo_session_owner_name_commit'),
    )
    op.create_index('idx_repositories_session', 'repositories', ['session_id'])

    # 3. analysis_jobs
    op.create_table(
        'analysis_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stage', sa.Text(), server_default='queued', nullable=False),
        sa.Column('progress', sa.SmallInteger(), server_default='0', nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("stage IN ('queued','fetching','parsing','indexing','embedding','ready','failed')"),
        sa.CheckConstraint('progress BETWEEN 0 AND 100'),
    )
    op.create_index('idx_jobs_repo', 'analysis_jobs', ['repository_id'])

    # 4. repo_files
    op.create_table(
        'repo_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('directory', sa.Text(), nullable=False),
        sa.Column('language', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('line_count', sa.Integer(), nullable=True),
        sa.Column('is_test', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('is_entry_point', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('content_tsv', postgresql.TSVECTOR(), nullable=True),
        sa.Column('sha1', sa.Text(), nullable=True),
        sa.UniqueConstraint('repository_id', 'path', name='uq_file_repo_path'),
    )
    op.create_index('idx_files_repo', 'repo_files', ['repository_id'])
    op.create_index('idx_files_tsv', 'repo_files', ['content_tsv'], postgresql_using='gin')
    op.execute("CREATE INDEX idx_files_path_trgm ON repo_files USING GIN (path gin_trgm_ops);")

    # 5. symbols
    op.create_table(
        'symbols',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('qualified_name', sa.Text(), nullable=True),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('docstring', sa.Text(), nullable=True),
        sa.Column('parent_symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id', ondelete='CASCADE'), nullable=True),
        sa.CheckConstraint("kind IN ('function','class','method','interface','type','variable','enum')"),
    )
    op.create_index('idx_symbols_repo_name', 'symbols', ['repository_id', 'name'])
    op.create_index('idx_symbols_file', 'symbols', ['file_id'])
    op.execute("CREATE INDEX idx_symbols_name_trgm ON symbols USING GIN (name gin_trgm_ops);")

    # 6. file_imports
    op.create_table(
        'file_imports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='SET NULL'), nullable=True),
        sa.Column('raw_specifier', sa.Text(), nullable=False),
        sa.Column('is_external', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('package_name', sa.Text(), nullable=True),
        sa.Column('line', sa.Integer(), nullable=True),
    )
    op.create_index('idx_imports_repo', 'file_imports', ['repository_id'])
    op.create_index('idx_imports_source', 'file_imports', ['source_file_id'])
    op.create_index('idx_imports_target', 'file_imports', ['target_file_id'])

    # 7. code_chunks
    op.create_table(
        'code_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id', ondelete='SET NULL'), nullable=True),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_estimate', sa.Integer(), nullable=True),
        sa.Column('content_tsv', postgresql.TSVECTOR(), nullable=True),
    )
    op.create_index('idx_chunks_repo', 'code_chunks', ['repository_id'])
    op.create_index('idx_chunks_tsv', 'code_chunks', ['content_tsv'], postgresql_using='gin')

    # 8. test_mappings
    op.create_table(
        'test_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('test_file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('method', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Text(), nullable=False),
        sa.CheckConstraint("method IN ('name_convention','import_analysis','directory_proximity')"),
        sa.CheckConstraint("confidence IN ('low','medium','high')"),
        sa.UniqueConstraint('source_file_id', 'test_file_id', name='uq_test_mapping'),
    )

    # 9. investigations
    op.create_table(
        'investigations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('repository_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('source_type', sa.Text(), nullable=False),
        sa.Column('issue_url', sa.Text(), nullable=True),
        sa.Column('issue_title', sa.Text(), nullable=True),
        sa.Column('issue_body', sa.Text(), nullable=False),
        sa.Column('extracted_terms', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.Column('status', sa.Text(), server_default='pending', nullable=False),
        sa.Column('evidence_strength', sa.Text(), nullable=True),
        sa.Column('hypotheses', postgresql.JSONB(), server_default='[]', nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("source_type IN ('text','github_issue')"),
        sa.CheckConstraint("status IN ('pending','processing','ready','failed')"),
        sa.CheckConstraint("evidence_strength IN ('weak','moderate','strong')"),
    )
    op.create_index('idx_investigations_repo', 'investigations', ['repository_id'])

    # 10. investigation_results
    op.create_table(
        'investigation_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('investigation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repo_files.id', ondelete='SET NULL'), nullable=True),
        sa.Column('symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id', ondelete='SET NULL'), nullable=True),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('retrieval_sources', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('why_relevant', sa.Text(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(), server_default='[]', nullable=False),
    )
    op.create_index('idx_inv_results_inv', 'investigation_results', ['investigation_id', 'rank'])

    # 11. contribution_plans
    op.create_table(
        'contribution_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('investigation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('plan', postgresql.JSONB(), nullable=False),
        sa.Column('markdown', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('contribution_plans')
    op.drop_table('investigation_results')
    op.drop_table('investigations')
    op.drop_table('test_mappings')
    op.drop_table('code_chunks')
    op.drop_table('file_imports')
    op.drop_table('symbols')
    op.drop_table('repo_files')
    op.drop_table('analysis_jobs')
    op.drop_table('repositories')
    op.drop_table('sessions')
