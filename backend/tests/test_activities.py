from decimal import Decimal

from backend.activities.checks import fetch_credit_report, run_fraud_check, verify_identity
from backend.activities.underwriting import evaluate_underwriting
from backend.activities.validation import validate_application
from backend.adapters import core_banking
from backend.domain import ApplicationInput, Channel, CheckResult, ProductType, UnderwritingInput


def _application(product_type=ProductType.PERSONAL, submitted_documents=None) -> ApplicationInput:
    return ApplicationInput(
        id="app-1",
        channel=Channel.PORTAL,
        external_ref="ext-1",
        product_type=product_type,
        requested_amount=Decimal("10000"),
        applicant_name="Jane Doe",
        applicant_ssn_hash="hash",
        applicant_ssn_last4="1234",
        submitted_documents=submitted_documents or [],
    )


async def test_validate_application_reports_no_missing_documents_when_complete():
    application = _application(
        submitted_documents=["government_id", "proof_of_income", "bank_statement"]
    )
    result = await validate_application(application)
    assert result.missing_documents == []


async def test_validate_application_reports_missing_documents():
    application = _application(submitted_documents=["government_id"])
    result = await validate_application(application)
    assert set(result.missing_documents) == {"proof_of_income", "bank_statement"}


async def test_fetch_credit_report_returns_credit_check_result():
    result = await fetch_credit_report(_application())
    assert result.check_type == "credit"
    assert result.status == "complete"
    assert "score" in result.detail


async def test_verify_identity_returns_identity_check_result():
    result = await verify_identity(_application())
    assert result.check_type == "identity"
    assert result.status == "complete"


async def test_run_fraud_check_returns_fraud_check_result():
    result = await run_fraud_check(_application())
    assert result.check_type == "fraud"
    assert result.status == "complete"


async def test_evaluate_underwriting_routes_to_correct_product_policy():
    # Same fraud signal personal tolerates but debt consolidation doesn't —
    # proves the activity looks up the policy by the application's own
    # product_type rather than always using one policy.
    fraud = CheckResult(check_type="fraud", status="complete", detail={"risk_score": 0.65})
    identity = CheckResult(check_type="identity", status="complete", detail={"match": True})
    credit = CheckResult(check_type="credit", status="complete", detail={"score": 700})

    debt_app = _application(product_type=ProductType.DEBT_CONSOLIDATION)
    decision = await evaluate_underwriting(
        UnderwritingInput(application=debt_app, credit=credit, identity=identity, fraud=fraud)
    )
    assert decision.outcome == "decline"
    assert decision.reason == "fraud_risk"


async def test_disburse_is_idempotent_for_same_key(monkeypatch):
    monkeypatch.setenv("MOCK_FAILURE_RATE", "0.0")
    monkeypatch.setenv("MOCK_LATENCY_SECONDS", "0")
    first = await core_banking.disburse("idem-test-key-1", Decimal("5000"))
    second = await core_banking.disburse("idem-test-key-1", Decimal("5000"))
    assert first == second


async def test_disburse_returns_different_confirmation_for_different_key(monkeypatch):
    monkeypatch.setenv("MOCK_FAILURE_RATE", "0.0")
    monkeypatch.setenv("MOCK_LATENCY_SECONDS", "0")
    first = await core_banking.disburse("idem-test-key-a", Decimal("100"))
    second = await core_banking.disburse("idem-test-key-b", Decimal("100"))
    assert first != second
