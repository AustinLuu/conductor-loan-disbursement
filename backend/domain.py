"""Shared domain types — workflow/activity payloads and API schemas.

These are plain Pydantic models so they cross the Temporal boundary via
temporalio.contrib.pydantic (see worker.py / api/main.py) as well as serve as
FastAPI request/response schemas. Not in the TDD's original repo layout as a
standalone file, but nearly every module needs these same shapes, so one
source of truth beats redefining them per module.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    AWAITING_DOCUMENTS = "AWAITING_DOCUMENTS"
    ENRICHING = "ENRICHING"
    UNDERWRITING = "UNDERWRITING"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    FUNDING = "FUNDING"
    FUNDED = "FUNDED"
    DECLINED = "DECLINED"
    ESCALATED = "ESCALATED"


class ProductType(str, Enum):
    PERSONAL = "personal"
    AUTO = "auto"
    DEBT_CONSOLIDATION = "debt_consolidation"


class Channel(str, Enum):
    PORTAL = "portal"
    BROKER_EMAIL = "broker_email"
    AGGREGATOR_BATCH = "aggregator_batch"


class ApplicationInput(BaseModel):
    """Canonical application shape every ingestion channel normalizes into."""

    id: str
    channel: Channel
    external_ref: str
    product_type: ProductType
    requested_amount: Decimal
    applicant_name: str
    applicant_ssn_hash: str
    applicant_ssn_last4: str
    submitted_documents: list[str] = Field(default_factory=list)


class BatchApplicationRecord(BaseModel):
    """One row of an aggregator batch drop, in canonical shape (TDD §5).
    Constructed manually inside BatchIngestionWorkflow from a raw dict so one
    malformed record can be rejected without failing the rest of the batch —
    letting FastAPI validate `list[BatchApplicationRecord]` directly at the
    API boundary would reject the entire request on the first bad row."""

    external_ref: str = Field(min_length=1)
    product_type: ProductType
    requested_amount: Decimal = Field(gt=0)
    applicant_name: str = Field(min_length=1)
    applicant_ssn: str = Field(pattern=r"^\d{9}$")
    submitted_documents: list[str] = Field(default_factory=list)


class BatchRecordResult(BaseModel):
    external_ref: str
    status: str  # "accepted" | "duplicate" | "duplicate_in_batch" | "rejected"
    application_id: str | None = None
    workflow_id: str | None = None
    reason: str = ""


class DocumentSubmission(BaseModel):
    doc_type: str
    storage_ref: str


class ReviewDecision(BaseModel):
    outcome: str  # "approve" | "decline" | "escalate"
    reason: str
    reviewer: str
    notes: str = ""


class ValidationResult(BaseModel):
    missing_documents: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    check_type: str  # "credit" | "identity" | "fraud"
    status: str  # "complete" | "failed"
    detail: dict = Field(default_factory=dict)


class UnderwritingInput(BaseModel):
    application: ApplicationInput
    credit: CheckResult
    identity: CheckResult
    fraud: CheckResult


class UnderwritingDecision(BaseModel):
    outcome: str  # "approve" | "decline" | "refer"
    reason: str


class DisburseInput(BaseModel):
    application_id: str
    amount: Decimal
    idempotency_key: str


class DisbursementResult(BaseModel):
    confirmation_id: str
    idempotency_key: str


class ReviewTaskInput(BaseModel):
    application_id: str
    reason: str


class DocumentStatusInput(BaseModel):
    application_id: str
    doc_type: str
    status: str  # "missing" | "received"
    storage_ref: str = ""


class AuditEventInput(BaseModel):
    application_id: str
    event_type: str
    actor: str
    detail: dict = Field(default_factory=dict)
    new_status: ApplicationStatus | None = None


class ApplicationResult(BaseModel):
    application_id: str
    status: ApplicationStatus
    reason: str = ""
