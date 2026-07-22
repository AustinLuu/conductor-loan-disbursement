"""Per-record activity BatchIngestionWorkflow calls to start an independent
LoanApplicationWorkflow for each aggregator-batch record (TDD §5) — not a
child workflow, so a redelivered batch file doesn't inflate the parent
workflow's own history, and a duplicate/already-started record is just an
ordinary caught exception on an independent client call (docs/05).
"""
from temporalio import activity
from temporalio.client import Client

from backend.domain import BatchApplicationRecord, BatchRecordResult, Channel
from backend.ingestion import start_application

_client: Client | None = None


def configure_client(client: Client) -> None:
    """Called once from worker.py after connecting. This activity needs a
    live Temporal client to start each record's LoanApplicationWorkflow, and
    activities can't receive one as a call argument — it isn't
    Temporal-serializable."""
    global _client
    _client = client


@activity.defn
async def start_application_workflow(record: BatchApplicationRecord) -> BatchRecordResult:
    assert _client is not None, "configure_client() must be called before the worker starts"
    outcome = await start_application(
        _client,
        channel=Channel.AGGREGATOR_BATCH,
        external_ref=record.external_ref,
        product_type=record.product_type,
        requested_amount=record.requested_amount,
        applicant_name=record.applicant_name,
        applicant_ssn=record.applicant_ssn,
        submitted_documents=record.submitted_documents,
    )
    return BatchRecordResult(
        external_ref=outcome.external_ref,
        status=outcome.status,
        application_id=outcome.application_id,
        workflow_id=outcome.workflow_id,
    )
