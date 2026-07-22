from backend.policies.base import LoanProductPolicy


class AutoLoanPolicy(LoanProductPolicy):
    def required_documents(self) -> list[str]:
        return ["government_id", "proof_of_income", "vehicle_purchase_agreement"]

    def risk_thresholds(self) -> dict[str, float]:
        # Slightly more lenient than personal: the vehicle is collateral.
        return {"min_credit_score": 620, "decline_below": 560, "max_fraud_risk": 0.7}
