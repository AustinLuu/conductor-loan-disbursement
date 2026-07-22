from backend.policies.base import LoanProductPolicy


class PersonalLoanPolicy(LoanProductPolicy):
    def required_documents(self) -> list[str]:
        return ["government_id", "proof_of_income", "bank_statement"]

    def risk_thresholds(self) -> dict[str, float]:
        return {"min_credit_score": 640, "decline_below": 580, "max_fraud_risk": 0.7}
