from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Integer, Text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    """Legacy boilerplate table — retained; superseded by Query + AnalysisStep."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class Dataset(Base):
    """An uploaded tabular file in the persistent library."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    source_format: Mapped[str] = mapped_column(Text, nullable=False, default="csv")
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    col_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ≤5 PII-masked rows — the ONLY rows allowed to reach the LLM.
    masked_sample: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class DatasetProfile(Base):
    """Auto-computed profile, one per dataset."""

    __tablename__ = "dataset_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(Text, nullable=False)
    # Per column: name, dtype, missing_count, distinct_count, min/max/range/mean, likely_pii
    columns: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class AnalysisSession(Base):
    """A long-lived conversation over one or more datasets (Phase 2).

    Named ``AnalysisSession`` to avoid a clash with ``sqlalchemy.orm.Session``;
    the table is ``sessions`` and it is exposed via ``/api/sessions``.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    # Active dataset ids for the session.
    dataset_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class Query(Base):
    """One natural-language question and its answer (id is also the graph run_id)."""

    __tablename__ = "queries"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataset_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumptions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    clarifying_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart_spec: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suggestions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class AnalysisStep(Base):
    """The audit trail — one row per executed code step."""

    __tablename__ = "analysis_steps"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    query_id: Mapped[str] = mapped_column(Text, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
