from decimal import Decimal

from backend.domain import ApplicationInput, Channel, CheckResult, ProductType
from backend.policies import get_product_policy


def _application(product_type: ProductType) -> ApplicationInput:
    return ApplicationInput(
        id="app-1",
        channel=Channel.PORTAL,
        external_ref="ext-1",
        product_type=product_type,
        requested_amount=Decimal("10000"),
        applicant_name="Jane Doe",
        applicant_ssn_hash="hash",
        applicant_ssn_last4="1234",
    )


def _check(check_type: str, status: str = "complete", **detail) -> CheckResult:
    return CheckResult(check_type=check_type, status=status, detail=detail)


def test_personal_policy_required_documents():
    policy = get_product_policy(ProductType.PERSONAL)
    assert policy.required_documents() == ["government_id", "proof_of_income", "bank_statement"]


def test_personal_policy_approves_strong_applicant():
    policy = get_product_policy(ProductType.PERSONAL)
    decision = policy.evaluate(
        _application(ProductType.PERSONAL),
        credit=_check("credit", score=700),
        identity=_check("identity", match=True, confidence=0.95),
        fraud=_check("fraud", risk_score=0.1),
    )
    assert decision.outcome == "approve"


def test_personal_policy_declines_identity_mismatch():
    policy = get_product_policy(ProductType.PERSONAL)
    decision = policy.evaluate(
        _application(ProductType.PERSONAL),
        credit=_check("credit", score=700),
        identity=_check("identity", match=False, confidence=0.2),
        fraud=_check("fraud", risk_score=0.1),
    )
    assert decision.outcome == "decline"
    assert decision.reason == "identity_mismatch"


def test_personal_policy_declines_low_credit_score():
    policy = get_product_policy(ProductType.PERSONAL)
    decision = policy.evaluate(
        _application(ProductType.PERSONAL),
        credit=_check("credit", score=500),
        identity=_check("identity", match=True, confidence=0.9),
        fraud=_check("fraud", risk_score=0.1),
    )
    assert decision.outcome == "decline"
    assert decision.reason == "credit_score_below_minimum"


def test_personal_policy_refers_borderline_credit_score():
    policy = get_product_policy(ProductType.PERSONAL)
    decision = policy.evaluate(
        _application(ProductType.PERSONAL),
        credit=_check("credit", score=610),
        identity=_check("identity", match=True, confidence=0.9),
        fraud=_check("fraud", risk_score=0.1),
    )
    assert decision.outcome == "refer"


def test_policy_refers_when_a_check_is_incomplete():
    policy = get_product_policy(ProductType.PERSONAL)
    decision = policy.evaluate(
        _application(ProductType.PERSONAL),
        credit=_check("credit", status="failed"),
        identity=_check("identity", match=True, confidence=0.9),
        fraud=_check("fraud", risk_score=0.1),
    )
    assert decision.outcome == "refer"
    assert decision.reason == "check_incomplete:credit"


def test_debt_consolidation_is_stricter_on_fraud_than_personal():
    # Same fraud signal: personal tolerates it, debt consolidation doesn't.
    fraud = _check("fraud", risk_score=0.65)
    identity = _check("identity", match=True, confidence=0.9)
    credit = _check("credit", score=700)

    personal = get_product_policy(ProductType.PERSONAL).evaluate(
        _application(ProductType.PERSONAL), credit, identity, fraud
    )
    debt = get_product_policy(ProductType.DEBT_CONSOLIDATION).evaluate(
        _application(ProductType.DEBT_CONSOLIDATION), credit, identity, fraud
    )

    assert personal.outcome == "approve"
    assert debt.outcome == "decline"
    assert debt.reason == "fraud_risk"
