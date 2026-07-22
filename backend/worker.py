import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from backend.activities.audit import record_audit_event
from backend.activities.batch_ingestion import configure_client, start_application_workflow
from backend.activities.checks import fetch_credit_report, run_fraud_check, verify_identity
from backend.activities.disbursement import disburse_funds
from backend.activities.documents import record_document_status
from backend.activities.review import create_review_task
from backend.activities.underwriting import evaluate_underwriting
from backend.activities.validation import validate_application
from backend.db.session import init_db
from backend.workflows.batch_ingestion_workflow import BatchIngestionWorkflow
from backend.workflows.loan_application_workflow import LoanApplicationWorkflow

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TASK_QUEUE = "loan-processing"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _connect_with_retry(max_attempts: int = 15, delay_seconds: float = 2.0) -> Client:
    # ponytail: docker-compose's service_healthy dependency should already
    # order this correctly; a short retry is cheap insurance against startup
    # races that healthchecks don't fully close.
    for attempt in range(1, max_attempts + 1):
        try:
            return await Client.connect(TEMPORAL_ADDRESS, data_converter=pydantic_data_converter)
        except RuntimeError:
            if attempt == max_attempts:
                raise
            logger.info(
                "Temporal not ready at %s (attempt %d/%d), retrying...",
                TEMPORAL_ADDRESS, attempt, max_attempts,
            )
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("unreachable")


async def main() -> None:
    await init_db()
    client = await _connect_with_retry()
    configure_client(client)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[LoanApplicationWorkflow, BatchIngestionWorkflow],
        activities=[
            validate_application,
            record_document_status,
            fetch_credit_report,
            verify_identity,
            run_fraud_check,
            evaluate_underwriting,
            create_review_task,
            disburse_funds,
            record_audit_event,
            start_application_workflow,
        ],
    )
    logger.info("Worker starting on task queue %r (%s)", TASK_QUEUE, TEMPORAL_ADDRESS)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
