from abc import ABC, abstractmethod

from backend.domain import ApplicationInput, CheckResult, UnderwritingDecision


class LoanProductPolicy(ABC):
    """One implementation per product_type. The workflow never branches on
    product type — it looks up a policy and delegates. See system design §6
    ('Product isolation')."""

    @abstractmethod
    def required_documents(self) -> list[str]: ...

    @abstractmethod
    def risk_thresholds(self) -> dict[str, float]: ...

    def evaluate(
        self,
        application: ApplicationInput,
        credit: CheckResult,
        identity: CheckResult,
        fraud: CheckResult,
    ) -> UnderwritingDecision:
        for check in (credit, identity, fraud):
            if check.status != "complete":
                return UnderwritingDecision(
                    outcome="refer", reason=f"check_incomplete:{check.check_type}"
                )

        if not identity.detail.get("match", False):
            return UnderwritingDecision(outcome="decline", reason="identity_mismatch")

        thresholds = self.risk_thresholds()
        if fraud.detail.get("risk_score", 0.0) >= thresholds["max_fraud_risk"]:
            return UnderwritingDecision(outcome="decline", reason="fraud_risk")

        score = credit.detail.get("score", 0)
        if score >= thresholds["min_credit_score"]:
            return UnderwritingDecision(outcome="approve", reason="auto_approved")
        if score < thresholds["decline_below"]:
            return UnderwritingDecision(
                outcome="decline", reason="credit_score_below_minimum"
            )
        return UnderwritingDecision(
            outcome="refer", reason="manual_underwriting_required"
        )
