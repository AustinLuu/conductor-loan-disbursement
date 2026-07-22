from backend.policies.base import LoanProductPolicy


class DebtConsolidationPolicy(LoanProductPolicy):
    def required_documents(self) -> list[str]:
        return ["government_id", "proof_of_income", "existing_debt_statement"]

    def risk_thresholds(self) -> dict[str, float]:
        # Unsecured and typically larger balances: stricter than personal/auto.
        return {"min_credit_score": 660, "decline_below": 600, "max_fraud_risk": 0.6}
