"""Shared "start one LoanApplicationWorkflow and persist its Application row"
core. Every channel that ingests a single application record — the portal
API route, the broker-email API route, and the per-record activity
BatchIngestionWorkflow calls for each row in an aggregator batch — calls
this same function rather than reimplementing it (system design §4.1: the
deterministic workflow ID + REJECT_DUPLICATE is the dedup mechanism, not
per-channel bookkeeping).
"""
import hashlib
import hmac
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from backend.db.models import Application
from backend.db.session import session_scope
from backend.domain import ApplicationInput, Channel, ProductType
from backend.workflows.loan_application_workflow import LoanApplicationWorkflow

_SSN_HASH_SECRET = os.environ.get("SSN_HASH_SECRET", "dev-only-secret-change-me").encode()
TASK_QUEUE = "loan-processing"


def hash_ssn(ssn: str) -> str:
    return hmac.new(_SSN_HASH_SECRET, ssn.encode(), hashlib.sha256).hexdigest()


@dataclass
class IngestOutcome:
    external_ref: str
    status: str  # "accepted" | "duplicate"
    application_id: str | None = None
    workflow_id: str | None = None


async def start_application(
    client: Client,
    *,
    channel: Channel,
    external_ref: str,
    product_type: ProductType,
    requested_amount: Decimal,
    applicant_name: str,
    applicant_ssn: str,
    submitted_documents: list[str],
) -> IngestOutcome:
    workflow_id = f"loan-app-{channel.value}-{external_ref}"
    application_id = str(uuid.uuid4())
    application_input = ApplicationInput(
        id=application_id,
        channel=channel,
        external_ref=external_ref,
        product_type=product_type,
        requested_amount=requested_amount,
        applicant_name=applicant_name,
        applicant_ssn_hash=hash_ssn(applicant_ssn),
        applicant_ssn_last4=applicant_ssn[-4:],
        submitted_documents=submitted_documents,
    )

    # Start the workflow FIRST — Temporal's own ID-uniqueness check is the
    # dedup mechanism (system design §4.1). Only persist to Postgres once
    # that's confirmed, so a rejected duplicate never leaves a phantom row.
    try:
        await client.start_workflow(
            LoanApplicationWorkflow.run,
            application_input,
            id=workflow_id,
            task_queue=TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        return IngestOutcome(external_ref=external_ref, status="duplicate", workflow_id=workflow_id)

    now = datetime.now(timezone.utc)
    async with session_scope() as session:
        session.add(
            Application(
                id=application_id,
                workflow_id=workflow_id,
                channel=channel.value,
                external_ref=external_ref,
                product_type=product_type.value,
                status="SUBMITTED",
                requested_amount=requested_amount,
                applicant_name=applicant_name,
                applicant_ssn_hash=application_input.applicant_ssn_hash,
                applicant_ssn_last4=application_input.applicant_ssn_last4,
                submitted_at=now,
                sla_deadline=now + timedelta(hours=48),
            )
        )

    return IngestOutcome(
        external_ref=external_ref,
        status="accepted",
        application_id=application_id,
        workflow_id=workflow_id,
    )
