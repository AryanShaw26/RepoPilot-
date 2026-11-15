import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    repositories: Mapped[List["Repository"]] = relationship(
        "Repository", back_populates="session", cascade="all, delete-orphan"
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", back_populates="session", cascade="all, delete-orphan"
    )


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(Text, nullable=False)
    commit_sha: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    license: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    size_kb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    languages: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    frameworks: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    entry_points: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    readme_excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    architecture_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, default="pending", nullable=False
    )
    snapshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(status.in_(["pending", "processing", "ready", "failed"])),
        UniqueConstraint("session_id", "owner", "name", "commit_sha", name="uq_repo_session_owner_name_commit"),
        Index("idx_repositories_session", "session_id"),
    )

    session: Mapped[Optional["SessionModel"]] = relationship(
        "SessionModel", back_populates="repositories"
    )
    jobs: Mapped[List["AnalysisJob"]] = relationship(
        "AnalysisJob", back_populates="repository", cascade="all, delete-orphan"
    )
    files: Mapped[List["RepoFile"]] = relationship(
        "RepoFile", back_populates="repository", cascade="all, delete-orphan"
    )
    symbols: Mapped[List["Symbol"]] = relationship(
        "Symbol", back_populates="repository", cascade="all, delete-orphan"
    )
    imports: Mapped[List["FileImport"]] = relationship(
        "FileImport", back_populates="repository", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk", back_populates="repository", cascade="all, delete-orphan"
    )
    test_mappings: Mapped[List["TestMapping"]] = relationship(
        "TestMapping", back_populates="repository", cascade="all, delete-orphan"
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", back_populates="repository", cascade="all, delete-orphan"
    )


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(
        Text, default="queued", nullable=False
    )
    progress: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            stage.in_(["queued", "fetching", "parsing", "indexing", "embedding", "ready", "failed"])
        ),
        CheckConstraint("progress BETWEEN 0 AND 100"),
        Index("idx_jobs_repo", "repository_id"),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="jobs")


class RepoFile(Base):
    __tablename__ = "repo_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    directory: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    line_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_entry_point: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_tsv = mapped_column(TSVECTOR, nullable=True)
    sha1: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("repository_id", "path", name="uq_file_repo_path"),
        Index("idx_files_repo", "repository_id"),
        Index("idx_files_tsv", "content_tsv", postgresql_using="gin"),
        Index("idx_files_path_trgm", "path", postgresql_using="gin", postgresql_ops={"path": "gin_trgm_ops"}),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="files")
    symbols: Mapped[List["Symbol"]] = relationship(
        "Symbol", back_populates="file", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk", back_populates="file", cascade="all, delete-orphan"
    )


class Symbol(Base):
    __tablename__ = "symbols"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qualified_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="CASCADE"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            kind.in_(["function", "class", "method", "interface", "type", "variable", "enum"])
        ),
        Index("idx_symbols_repo_name", "repository_id", "name"),
        Index("idx_symbols_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("idx_symbols_file", "file_id"),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="symbols")
    file: Mapped["RepoFile"] = relationship("RepoFile", back_populates="symbols")
    parent_symbol: Mapped[Optional["Symbol"]] = relationship("Symbol", remote_side=[id])


class FileImport(Base):
    __tablename__ = "file_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False
    )
    target_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="SET NULL"), nullable=True
    )
    raw_specifier: Mapped[str] = mapped_column(Text, nullable=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    package_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_imports_repo", "repository_id"),
        Index("idx_imports_source", "source_file_id"),
        Index("idx_imports_target", "target_file_id"),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="imports")
    source_file: Mapped["RepoFile"] = relationship("RepoFile", foreign_keys=[source_file_id])
    target_file: Mapped[Optional["RepoFile"]] = relationship("RepoFile", foreign_keys=[target_file_id])


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False
    )
    symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_tsv = mapped_column(TSVECTOR, nullable=True)
    # embedding column is NOT declared in ORM per PRD §7.3; added by migration 0002

    __table_args__ = (
        Index("idx_chunks_repo", "repository_id"),
        Index("idx_chunks_tsv", "content_tsv", postgresql_using="gin"),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="chunks")
    file: Mapped["RepoFile"] = relationship("RepoFile", back_populates="chunks")
    symbol: Mapped[Optional["Symbol"]] = relationship("Symbol")


class TestMapping(Base):
    __tablename__ = "test_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False
    )
    test_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="CASCADE"), nullable=False
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(method.in_(["name_convention", "import_analysis", "directory_proximity"])),
        CheckConstraint(confidence.in_(["low", "medium", "high"])),
        UniqueConstraint("source_file_id", "test_file_id", name="uq_test_mapping"),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="test_mappings")
    source_file: Mapped["RepoFile"] = relationship("RepoFile", foreign_keys=[source_file_id])
    test_file: Mapped["RepoFile"] = relationship("RepoFile", foreign_keys=[test_file_id])


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    issue_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issue_body: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_terms: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    evidence_strength: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hypotheses: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(source_type.in_(["text", "github_issue"])),
        CheckConstraint(status.in_(["pending", "processing", "ready", "failed"])),
        CheckConstraint(evidence_strength.in_(["weak", "moderate", "strong"])),
        Index("idx_investigations_repo", "repository_id"),
    )

    repository: Mapped["Repository"] = relationship("Repository", back_populates="investigations")
    session: Mapped[Optional["SessionModel"]] = relationship("SessionModel", back_populates="investigations")
    results: Mapped[List["InvestigationResult"]] = relationship(
        "InvestigationResult", back_populates="investigation", cascade="all, delete-orphan", order_by="InvestigationResult.rank"
    )
    plans: Mapped[List["ContributionPlan"]] = relationship(
        "ContributionPlan", back_populates="investigation", cascade="all, delete-orphan"
    )


class InvestigationResult(Base):
    __tablename__ = "investigation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("repo_files.id", ondelete="SET NULL"), nullable=True
    )
    symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("symbols.id", ondelete="SET NULL"), nullable=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    retrieval_sources: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False)
    why_relevant: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)

    __table_args__ = (
        Index("idx_inv_results_inv", "investigation_id", "rank"),
    )

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="results")
    file: Mapped[Optional["RepoFile"]] = relationship("RepoFile")
    symbol: Mapped[Optional["Symbol"]] = relationship("Symbol")


class ContributionPlan(Base):
    __tablename__ = "contribution_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    user_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="plans")
