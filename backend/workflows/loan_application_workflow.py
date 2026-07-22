"""LoanApplicationWorkflow — TDD §3.

Validate -> enrich (parallel third-party checks) -> underwrite ->
[human review if referred] -> fund / decline / escalate.

The TDD's code sample is explicitly "trimmed for readability" and doesn't
match the real SDK signatures 1:1 (activities take a single input, not
positional args; wait_condition raises TimeoutError rather than returning
false; policy lookup happens inside activities, not passed from the
workflow — see system design §6 "Product isolation"). This is the real,
adapted version.
"""
import asyncio
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from backend.activities.audit import record_audit_event
    from backend.activities.checks import fetch_credit_report, run_fraud_check, verify_identity
    from backend.activities.disbursement import disburse_funds
    from backend.activities.documents import record_document_status
    from backend.activities.review import create_review_task
    from backend.activities.underwriting import evaluate_underwriting
    from backend.activities.validation import validate_application
    from backend.domain import (
        ApplicationInput,
        ApplicationResult,
        ApplicationStatus,
        AuditEventInput,
        CheckResult,
        DisburseInput,
        DocumentStatusInput,
        DocumentSubmission,
        ReviewDecision,
        ReviewTaskInput,
        UnderwritingInput,
    )

THIRD_PARTY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=5,
    non_retryable_error_types=["InvalidApplicationDataError"],
)

_ACTIVITY_TIMEOUT = timedelta(seconds=30)
_THIRD_PARTY_TIMEOUT = timedelta(minutes=5)
_SLA_HOURS = 48


@workflow.defn
class LoanApplicationWorkflow:
    def __init__(self) -> None:
        self.status: ApplicationStatus = ApplicationStatus.SUBMITTED
        self.documents_received: dict[str, bool] = {}
        self.review_decision: ReviewDecision | None = None
        self.sla_deadline: datetime | None = None

    @workflow.run
    async def run(self, application: ApplicationInput) -> ApplicationResult:
        self.sla_deadline = workflow.now() + timedelta(hours=_SLA_HOURS)

        # 1. Validate
        validation = await workflow.execute_activity(
            validate_application, application, start_to_close_timeout=_ACTIVITY_TIMEOUT
        )
        if validation.missing_documents:
            self.status = ApplicationStatus.AWAITING_DOCUMENTS
            await self._audit(application, "status_changed", "system", {}, new_status=self.status)
            for doc_type in validation.missing_documents:
                await workflow.execute_activity(
                    record_document_status,
                    DocumentStatusInput(
                        application_id=application.id, doc_type=doc_type, status="missing"
                    ),
                    start_to_close_timeout=_ACTIVITY_TIMEOUT,
                )
            try:
                await workflow.wait_condition(
                    lambda: all(
                        self.documents_received.get(d) for d in validation.missing_documents
                    ),
                    timeout=self._remaining_sla(),
                )
            except asyncio.TimeoutError:
                pass
            if not all(self.documents_received.get(d) for d in validation.missing_documents):
                return await self._decline(application, "documents_not_received")

        # 2. Enrich — parallel third-party checks, each with its own retry policy
        self.status = ApplicationStatus.ENRICHING
        await self._audit(application, "status_changed", "system", {}, new_status=self.status)
        credit, identity, fraud = await asyncio.gather(
            workflow.execute_activity(
                fetch_credit_report,
                application,
                retry_policy=THIRD_PARTY_RETRY,
                start_to_close_timeout=_THIRD_PARTY_TIMEOUT,
            ),
            workflow.execute_activity(
                verify_identity,
                application,
                retry_policy=THIRD_PARTY_RETRY,
                start_to_close_timeout=_THIRD_PARTY_TIMEOUT,
            ),
            workflow.execute_activity(
                run_fraud_check,
                application,
                retry_policy=THIRD_PARTY_RETRY,
                start_to_close_timeout=_THIRD_PARTY_TIMEOUT,
            ),
            return_exceptions=True,
        )
        credit = self._as_check_result(credit, "credit")
        identity = self._as_check_result(identity, "identity")
        fraud = self._as_check_result(fraud, "fraud")

        # 3. Underwrite
        self.status = ApplicationStatus.UNDERWRITING
        await self._audit(application, "status_changed", "system", {}, new_status=self.status)
        decision = await workflow.execute_activity(
            evaluate_underwriting,
            UnderwritingInput(application=application, credit=credit, identity=identity, fraud=fraud),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
        )
        await self._audit(
            application,
            "underwriting_decision",
            "system",
            {
                "outcome": decision.outcome,
                "reason": decision.reason,
                "credit": credit.detail,
                "identity": identity.detail,
                "fraud": fraud.detail,
            },
        )

        if decision.outcome == "approve":
            return await self._fund(application)
        if decision.outcome == "decline":
            return await self._decline(application, decision.reason)

        # 4. Human review
        self.status = ApplicationStatus.NEEDS_HUMAN_REVIEW
        await self._audit(application, "status_changed", "system", {}, new_status=self.status)
        await workflow.execute_activity(
            create_review_task,
            ReviewTaskInput(application_id=application.id, reason=decision.reason),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
        )
        try:
            await workflow.wait_condition(
                lambda: self.review_decision is not None,
                timeout=self._remaining_sla(),
            )
        except asyncio.TimeoutError:
            pass
        if self.review_decision is None:
            return await self._escalate(application, "review_timeout")
        if self.review_decision.outcome == "approve":
            return await self._fund(application)
        if self.review_decision.outcome == "decline":
            return await self._decline(application, self.review_decision.reason)
        return await self._escalate(application, self.review_decision.reason)

    @workflow.signal
    async def submit_document(self, doc: DocumentSubmission) -> None:
        self.documents_received[doc.doc_type] = True

    @workflow.signal
    async def submit_review_decision(self, decision: ReviewDecision) -> None:
        self.review_decision = decision

    @workflow.query
    def get_status(self) -> str:
        return self.status.value

    @workflow.query
    def get_sla_remaining(self) -> float:
        return self._remaining_sla().total_seconds()

    def _remaining_sla(self) -> timedelta:
        return max(self.sla_deadline - workflow.now(), timedelta(0))

    @staticmethod
    def _as_check_result(value, check_type: str) -> CheckResult:
        if isinstance(value, CheckResult):
            return value
        return CheckResult(check_type=check_type, status="failed", detail={"error": str(value)})

    async def _audit(
        self, application: ApplicationInput, event_type: str, actor: str, detail: dict,
        new_status: ApplicationStatus | None = None,
    ) -> None:
        await workflow.execute_activity(
            record_audit_event,
            AuditEventInput(
                application_id=application.id,
                event_type=event_type,
                actor=actor,
                detail=detail,
                new_status=new_status,
            ),
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
        )

    async def _fund(self, application: ApplicationInput) -> ApplicationResult:
        self.status = ApplicationStatus.FUNDING
        await self._audit(application, "status_changed", "system", {}, new_status=self.status)
        idempotency_key = str(workflow.uuid4())
        try:
            await workflow.execute_activity(
                disburse_funds,
                DisburseInput(
                    application_id=application.id,
                    amount=application.requested_amount,
                    idempotency_key=idempotency_key,
                ),
                retry_policy=THIRD_PARTY_RETRY,
                start_to_close_timeout=_THIRD_PARTY_TIMEOUT,
            )
        except ActivityError:
            return await self._escalate(application, "disbursement_failed")
        self.status = ApplicationStatus.FUNDED
        await self._audit(application, "application_funded", "system", {}, new_status=self.status)
        return ApplicationResult(application_id=application.id, status=self.status)

    async def _decline(self, application: ApplicationInput, reason: str) -> ApplicationResult:
        self.status = ApplicationStatus.DECLINED
        await self._audit(
            application, "application_declined", "system", {"reason": reason}, new_status=self.status
        )
        return ApplicationResult(application_id=application.id, status=self.status, reason=reason)

    async def _escalate(self, application: ApplicationInput, reason: str) -> ApplicationResult:
        self.status = ApplicationStatus.ESCALATED
        await self._audit(
            application, "application_escalated", "system", {"reason": reason}, new_status=self.status
        )
        return ApplicationResult(application_id=application.id, status=self.status, reason=reason)
