"""Application intake (portal + broker-email) and review/audit endpoints
(TDD §3.1). Aggregator-batch intake lives in the routes below too, backed by
BatchIngestionWorkflow — see backend/workflows/batch_ingestion_workflow.py."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from temporalio.client import Client

from backend.db.models import Application, AuditEvent, Check, Document, ReviewTask
from backend.db.session import session_scope
from backend.domain import (
    Channel,
    DocumentSubmission,
    ProductType,
    ReviewDecision,
)
from backend.ingestion import start_application
from backend.workflows.loan_application_workflow import LoanApplicationWorkflow

router = APIRouter()

_TASK_QUEUE = "loan-processing"


def get_temporal_client(request: Request) -> Client:
    return request.app.state.temporal_client


def _application_summary(a: Application) -> dict:
    return {
        "id": a.id,
        "workflow_id": a.workflow_id,
        "channel": a.channel,
        "product_type": a.product_type,
        "status": a.status,
        "requested_amount": str(a.requested_amount),
        "submitted_at": a.submitted_at.isoformat(),
        "sla_deadline": a.sla_deadline.isoformat(),
    }


class PortalApplicationSubmission(BaseModel):
    # The portal's own idempotency key for this submission (e.g. a
    # client-generated form-session id) — resubmitting the same value is
    # what a flaky-network double-click looks like, and it's what the
    # deterministic workflow ID dedups against (system design §4.1).
    external_ref: str = Field(min_length=1)
    product_type: ProductType
    requested_amount: Decimal = Field(gt=0)
    applicant_name: str = Field(min_length=1)
    applicant_ssn: str = Field(pattern=r"^\d{9}$")
    submitted_documents: list[str] = Field(default_factory=list)


class BrokerEmailSubmission(BaseModel):
    # message_id is the broker email's own natural key — same idempotency
    # role external_ref plays for the portal (system design §4.1).
    message_id: str = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    product_type: ProductType
    requested_amount: Decimal = Field(gt=0)
    applicant_name: str = Field(min_length=1)
    applicant_ssn: str = Field(pattern=r"^\d{9}$")
    submitted_documents: list[str] = Field(default_factory=list)


class ReviewDecisionSubmission(BaseModel):
    outcome: str  # approve | decline | escalate
    reason: str
    reviewer: str
    notes: str = ""


@router.post("/applications")
async def submit_application(
    submission: PortalApplicationSubmission,
    client: Client = Depends(get_temporal_client),
) -> dict:
    outcome = await start_application(
        client,
        channel=Channel.PORTAL,
        external_ref=submission.external_ref,
        product_type=submission.product_type,
        requested_amount=submission.requested_amount,
        applicant_name=submission.applicant_name,
        applicant_ssn=submission.applicant_ssn,
        submitted_documents=submission.submitted_documents,
    )
    if outcome.status == "duplicate":
        raise HTTPException(
            409, f"an application with external_ref {submission.external_ref!r} already exists"
        )
    return {"application_id": outcome.application_id, "workflow_id": outcome.workflow_id}


@router.post("/ingest/broker-email")
async def ingest_broker_email(
    submission: BrokerEmailSubmission,
    client: Client = Depends(get_temporal_client),
) -> dict:
    outcome = await start_application(
        client,
        channel=Channel.BROKER_EMAIL,
        external_ref=submission.message_id,
        product_type=submission.product_type,
        requested_amount=submission.requested_amount,
        applicant_name=submission.applicant_name,
        applicant_ssn=submission.applicant_ssn,
        submitted_documents=submission.submitted_documents,
    )
    if outcome.status == "duplicate":
        raise HTTPException(
            409, f"an application with message_id {submission.message_id!r} already exists"
        )
    return {
        "application_id": outcome.application_id,
        "workflow_id": outcome.workflow_id,
        "broker_name": submission.broker_name,
    }


@router.get("/applications")
async def list_applications(status: str | None = None) -> list[dict]:
    async with session_scope() as session:
        stmt = select(Application)
        if status:
            stmt = stmt.where(Application.status == status)
        rows = (await session.scalars(stmt)).all()
        return [_application_summary(a) for a in rows]


@router.get("/applications/{application_id}")
async def get_application(application_id: str) -> dict:
    async with session_scope() as session:
        application = await session.get(Application, application_id)
        if application is None:
            raise HTTPException(404, "application not found")
        documents = (
            await session.scalars(select(Document).where(Document.application_id == application_id))
        ).all()
        checks = (
            await session.scalars(select(Check).where(Check.application_id == application_id))
        ).all()
        audit_events = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.application_id == application_id)
                .order_by(AuditEvent.occurred_at)
            )
        ).all()
        return {
            **_application_summary(application),
            "documents": [{"doc_type": d.doc_type, "status": d.status} for d in documents],
            "checks": [
                {"check_type": c.check_type, "status": c.status, "result": c.result} for c in checks
            ],
            "audit_events": [
                {
                    "event_type": e.event_type,
                    "actor": e.actor,
                    "detail": e.detail,
                    "occurred_at": e.occurred_at.isoformat(),
                }
                for e in audit_events
            ],
        }


@router.post("/applications/{application_id}/documents")
async def submit_document(
    application_id: str,
    submission: DocumentSubmission,
    client: Client = Depends(get_temporal_client),
) -> dict:
    async with session_scope() as session:
        application = await session.get(Application, application_id)
        if application is None:
            raise HTTPException(404, "application not found")
        existing = await session.scalar(
            select(Document).where(
                Document.application_id == application_id,
                Document.doc_type == submission.doc_type,
            )
        )
        if existing:
            existing.status = "received"
            existing.storage_ref = submission.storage_ref
        else:
            session.add(
                Document(
                    application_id=application_id,
                    doc_type=submission.doc_type,
                    status="received",
                    storage_ref=submission.storage_ref,
                )
            )
        workflow_id = application.workflow_id

    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(LoanApplicationWorkflow.submit_document, submission)
    return {"status": "received"}


@router.get("/reviews")
async def list_reviews(status: str = "pending") -> list[dict]:
    async with session_scope() as session:
        rows = (
            await session.scalars(select(ReviewTask).where(ReviewTask.status == status))
        ).all()
        return [
            {"id": r.id, "application_id": r.application_id, "reason": r.reason, "status": r.status}
            for r in rows
        ]


@router.post("/reviews/{review_id}/decision")
async def submit_review_decision(
    review_id: str,
    submission: ReviewDecisionSubmission,
    client: Client = Depends(get_temporal_client),
) -> dict:
    async with session_scope() as session:
        review_task = await session.get(ReviewTask, review_id)
        if review_task is None:
            raise HTTPException(404, "review task not found")
        application = await session.get(Application, review_task.application_id)
        if application is None:
            raise HTTPException(404, "application not found")
        workflow_id = application.workflow_id

    # Signal before marking "decided" — if the signal fails, the review
    # stays "pending" instead of being orphaned in a decided-but-not-signaled
    # state (see project memory: bug_review_decision_ordering).
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(
        LoanApplicationWorkflow.submit_review_decision,
        ReviewDecision(
            outcome=submission.outcome,
            reason=submission.reason,
            reviewer=submission.reviewer,
            notes=submission.notes,
        ),
    )

    async with session_scope() as session:
        review_task = await session.get(ReviewTask, review_id)
        review_task.status = "decided"
        review_task.decision = submission.outcome
        review_task.notes = submission.notes

    return {"status": "signaled"}


@router.get("/audit/{application_id}")
async def get_audit_trail(application_id: str) -> list[dict]:
    async with session_scope() as session:
        rows = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.application_id == application_id)
                .order_by(AuditEvent.occurred_at)
            )
        ).all()
        return [
            {
                "event_type": e.event_type,
                "actor": e.actor,
                "detail": e.detail,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in rows
        ]
