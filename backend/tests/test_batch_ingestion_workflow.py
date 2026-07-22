import uuid

from temporalio import activity
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from backend.domain import BatchApplicationRecord, BatchRecordResult
from backend.workflows.batch_ingestion_workflow import BatchIngestionWorkflow

TASK_QUEUE = "test-batch-ingestion"


def _valid_record(external_ref="rec-1", **overrides):
    defaults = dict(
        external_ref=external_ref,
        product_type="personal",
        requested_amount="10000",
        applicant_name="Jane Doe",
        applicant_ssn="123456789",
        submitted_documents=["government_id", "proof_of_income", "bank_statement"],
    )
    defaults.update(overrides)
    return defaults


def _mock_start_activity(calls: list):
    @activity.defn(name="start_application_workflow")
    async def start_application_workflow(record: BatchApplicationRecord) -> BatchRecordResult:
        calls.append(record.external_ref)
        return BatchRecordResult(
            external_ref=record.external_ref,
            status="accepted",
            application_id=f"app-{record.external_ref}",
            workflow_id=f"loan-app-aggregator_batch-{record.external_ref}",
        )

    return start_application_workflow


async def test_batch_starts_one_workflow_per_valid_record():
    calls: list[str] = []
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[BatchIngestionWorkflow],
            activities=[_mock_start_activity(calls)],
        ):
            records = [_valid_record("rec-1"), _valid_record("rec-2"), _valid_record("rec-3")]
            results = await env.client.execute_workflow(
                BatchIngestionWorkflow.run,
                records,
                id=f"batch-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert calls == ["rec-1", "rec-2", "rec-3"]
    assert [r.status for r in results] == ["accepted", "accepted", "accepted"]


async def test_batch_rejects_invalid_record_without_aborting_others():
    calls: list[str] = []
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[BatchIngestionWorkflow],
            activities=[_mock_start_activity(calls)],
        ):
            records = [
                _valid_record("rec-1"),
                _valid_record("rec-2", applicant_ssn="not-a-ssn"),
                _valid_record("rec-3"),
            ]
            results = await env.client.execute_workflow(
                BatchIngestionWorkflow.run,
                records,
                id=f"batch-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert calls == ["rec-1", "rec-3"]
    assert [r.status for r in results] == ["accepted", "rejected", "accepted"]
    assert results[1].reason


async def test_batch_dedupes_same_external_ref_within_one_batch():
    calls: list[str] = []
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[BatchIngestionWorkflow],
            activities=[_mock_start_activity(calls)],
        ):
            records = [_valid_record("rec-1"), _valid_record("rec-1")]
            results = await env.client.execute_workflow(
                BatchIngestionWorkflow.run,
                records,
                id=f"batch-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert calls == ["rec-1"]
    assert [r.status for r in results] == ["accepted", "duplicate_in_batch"]
