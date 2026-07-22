"""SQLAlchemy models mirroring the 5-table entity model in
docs/02-system-design.md §2. Postgres owns the data the API/dashboard query;
Temporal owns the process (see system design §4.4)."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    workflow_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    channel: Mapped[str] = mapped_column(String)
    external_ref: Mapped[str] = mapped_column(String)
    product_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    applicant_name: Mapped[str] = mapped_column(String)
    applicant_ssn_hash: Mapped[str] = mapped_column(String)
    applicant_ssn_last4: Mapped[str] = mapped_column(String(4))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    storage_ref: Mapped[str] = mapped_column(String, default="")


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    check_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    decision: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    event_type: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
