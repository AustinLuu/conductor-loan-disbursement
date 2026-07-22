import asyncio
import uuid
from decimal import Decimal

from temporalio import activity
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from backend.domain import (
    ApplicationInput,
    ApplicationStatus,
    AuditEventInput,
    Channel,
    CheckResult,
    DisburseInput,
    DisbursementResult,
    DocumentStatusInput,
    ProductType,
    ReviewDecision,
    ReviewTaskInput,
    UnderwritingDecision,
    UnderwritingInput,
    ValidationResult,
)
from backend.workflows.loan_application_workflow import LoanApplicationWorkflow

TASK_QUEUE = "test-loan-processing"


def _application(**overrides) -> ApplicationInput:
    defaults = dict(
        id=f"app-{uuid.uuid4()}",
        channel=Channel.PORTAL,
        external_ref="ext-1",
        product_type=ProductType.PERSONAL,
        requested_amount=Decimal("10000"),
        applicant_name="Jane Doe",
        applicant_ssn_hash="hash",
        applicant_ssn_last4="1234",
        submitted_documents=["government_id", "proof_of_income", "bank_statement"],
    )
    defaults.update(overrides)
    return ApplicationInput(**defaults)


def _mock_activities(underwriting_outcome="approve", underwriting_reason="auto_approved"):
    """Stand-ins for the real activities (which hit adapters/Postgres), keyed
    to match by name so the *real* workflow code needs no test-only branches
    (TDD §7)."""

    @activity.defn(name="validate_application")
    async def validate(application: ApplicationInput) -> ValidationResult:
        return ValidationResult(missing_documents=[])

    @activity.defn(name="record_document_status")
    async def record_document(input: DocumentStatusInput) -> None:
        return None

    @activity.defn(name="fetch_credit_report")
    async def credit(application: ApplicationInput) -> CheckResult:
        return CheckResult(check_type="credit", status="complete", detail={"score": 750})

    @activity.defn(name="verify_identity")
    async def identity(application: ApplicationInput) -> CheckResult:
        return CheckResult(check_type="identity", status="complete", detail={"match": True})

    @activity.defn(name="run_fraud_check")
    async def fraud(application: ApplicationInput) -> CheckResult:
        return CheckResult(check_type="fraud", status="complete", detail={"risk_score": 0.05})

    @activity.defn(name="evaluate_underwriting")
    async def underwrite(input: UnderwritingInput) -> UnderwritingDecision:
        return UnderwritingDecision(outcome=underwriting_outcome, reason=underwriting_reason)

    @activity.defn(name="create_review_task")
    async def review_task(input: ReviewTaskInput) -> None:
        return None

    @activity.defn(name="disburse_funds")
    async def disburse(input: DisburseInput) -> DisbursementResult:
        return DisbursementResult(
            confirmation_id="conf-test", idempotency_key=input.idempotency_key
        )

    @activity.defn(name="record_audit_event")
    async def audit(input: AuditEventInput) -> None:
        return None

    return [validate, record_document, credit, identity, fraud, underwrite, review_task, disburse, audit]


async def test_auto_approve_happy_path_funds_the_application():
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[LoanApplicationWorkflow],
            activities=_mock_activities(underwriting_outcome="approve"),
        ):
            result = await env.client.execute_workflow(
                LoanApplicationWorkflow.run,
                _application(),
                id=f"wf-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert result.status == ApplicationStatus.FUNDED


async def test_auto_decline_terminal_state():
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[LoanApplicationWorkflow],
            activities=_mock_activities(
                underwriting_outcome="decline", underwriting_reason="credit_score_below_minimum"
            ),
        ):
            result = await env.client.execute_workflow(
                LoanApplicationWorkflow.run,
                _application(),
                id=f"wf-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert result.status == ApplicationStatus.DECLINED
    assert result.reason == "credit_score_below_minimum"


async def test_human_review_approve_via_signal_resumes_and_funds():
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[LoanApplicationWorkflow],
            activities=_mock_activities(
                underwriting_outcome="refer", underwriting_reason="manual_underwriting_required"
            ),
        ):
            handle = await env.client.start_workflow(
                LoanApplicationWorkflow.run,
                _application(),
                id=f"wf-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
            for _ in range(100):
                status = await handle.query(LoanApplicationWorkflow.get_status)
                if status == ApplicationStatus.NEEDS_HUMAN_REVIEW.value:
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached NEEDS_HUMAN_REVIEW")

            await handle.signal(
                LoanApplicationWorkflow.submit_review_decision,
                ReviewDecision(outcome="approve", reason="looks_fine", reviewer="ops1"),
            )
            result = await handle.result()
    assert result.status == ApplicationStatus.FUNDED


async def test_human_review_timeout_escalates():
    async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[LoanApplicationWorkflow],
            activities=_mock_activities(
                underwriting_outcome="refer", underwriting_reason="manual_underwriting_required"
            ),
        ):
            # No signal sent — the time-skipping server fast-forwards through
            # the 48h SLA wait so this resolves in real milliseconds.
            result = await env.client.execute_workflow(
                LoanApplicationWorkflow.run,
                _application(),
                id=f"wf-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert result.status == ApplicationStatus.ESCALATED
    assert result.reason == "review_timeout"
