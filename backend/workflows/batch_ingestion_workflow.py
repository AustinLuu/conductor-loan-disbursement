"""BatchIngestionWorkflow — TDD §5.

Parses/validates/dedupes an aggregator batch drop, then starts one
independent LoanApplicationWorkflow per valid record via an activity (not a
child workflow — see the module docstring on
backend/activities/batch_ingestion.py for why). Returns one
accepted/duplicate/rejected result per input record, matching the PRD's
per-record success/failure requirement for the aggregator channel.
"""
from datetime import timedelta

from pydantic import ValidationError
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from backend.activities.batch_ingestion import start_application_workflow
    from backend.domain import BatchApplicationRecord, BatchRecordResult


def _describe_validation_error(exc: ValidationError) -> str:
    # str(exc) includes each field's raw input_value — for applicant_ssn
    # that's the rejected SSN itself. include_input=False keeps the reason
    # human-readable without echoing applicant PII back through the API.
    return "; ".join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
        for err in exc.errors(include_url=False, include_input=False)
    )


@workflow.defn
class BatchIngestionWorkflow:
    @workflow.run
    async def run(self, records: list[dict]) -> list[BatchRecordResult]:
        results: list[BatchRecordResult] = []
        seen_refs: set[str] = set()

        for raw in records:
            external_ref = str(raw.get("external_ref", ""))

            if external_ref in seen_refs:
                results.append(
                    BatchRecordResult(external_ref=external_ref, status="duplicate_in_batch")
                )
                continue

            try:
                record = BatchApplicationRecord(**raw)
            except ValidationError as exc:
                results.append(
                    BatchRecordResult(
                        external_ref=external_ref,
                        status="rejected",
                        reason=_describe_validation_error(exc),
                    )
                )
                continue

            seen_refs.add(external_ref)
            try:
                result = await workflow.execute_activity(
                    start_application_workflow,
                    record,
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
            except ActivityError as exc:
                result = BatchRecordResult(
                    external_ref=external_ref, status="failed", reason=str(exc)
                )
            results.append(result)

        return results
