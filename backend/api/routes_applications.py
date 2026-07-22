"""Portal application intake + review endpoints (TDD §3.1). Broker-email and
aggregator-batch intake (routes_ingestion.py, BatchIngestionWorkflow) are out
of scope for this pass — see the summary in chat; the portal channel alone is
enough to prove the orchestration model, matching the disciplined-2-hour
scope call in docs/06-timeboxing-and-approach.md."""
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from temporalio.client import Client

from backend.db.models import Application, AuditEvent, Check, Document, ReviewTask
from backend.db.session import session_scope
from backend.domain import (
    ApplicationInput,
    Channel,
    DocumentSubmission,
    ProductType,
    ReviewDecision,
)
from backend.workflows.loan_application_workflow import LoanApplicationWorkflow

router = APIRouter()

_SSN_HASH_SECRET = os.environ.get("SSN_HASH_SECRET", "dev-only-secret-change-me").encode()
_TASK_QUEUE = "loan-processing"


def _hash_ssn(ssn: str) -> str:
    return hmac.new(_SSN_HASH_SECRET, ssn.encode(), hashlib.sha256).hexdigest()


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
    application_id = str(uuid.uuid4())
    workflow_id = f"loan-app-portal-{application_id}"

    application_input = ApplicationInput(
        id=application_id,
        channel=Channel.PORTAL,
        external_ref=application_id,
        product_type=submission.product_type,
        requested_amount=submission.requested_amount,
        applicant_name=submission.applicant_name,
        applicant_ssn_hash=_hash_ssn(submission.applicant_ssn),
        applicant_ssn_last4=submission.applicant_ssn[-4:],
        submitted_documents=submission.submitted_documents,
    )

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        session.add(
            Application(
                id=application_id,
                workflow_id=workflow_id,
                channel=Channel.PORTAL.value,
                external_ref=application_id,
                product_type=submission.product_type.value,
                status="SUBMITTED",
                requested_amount=submission.requested_amount,
                applicant_name=submission.applicant_name,
                applicant_ssn_hash=application_input.applicant_ssn_hash,
                applicant_ssn_last4=application_input.applicant_ssn_last4,
                submitted_at=now,
                sla_deadline=now + timedelta(hours=48),
            )
        )

    await client.start_workflow(
        LoanApplicationWorkflow.run,
        application_input,
        id=workflow_id,
        task_queue=_TASK_QUEUE,
    )
    return {"application_id": application_id, "workflow_id": workflow_id}


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
        review_task.status = "decided"
        review_task.decision = submission.outcome
        review_task.notes = submission.notes
        application = await session.get(Application, review_task.application_id)
        if application is None:
            raise HTTPException(404, "application not found")
        workflow_id = application.workflow_id

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
