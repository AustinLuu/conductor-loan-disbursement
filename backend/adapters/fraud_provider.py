import random

from backend.adapters.mock_support import maybe_fail, simulate_latency
from backend.domain import ApplicationInput, CheckResult


async def run_fraud_check(application: ApplicationInput) -> CheckResult:
    await simulate_latency()
    maybe_fail("fraud_provider")
    risk_score = round(random.uniform(0.0, 0.3), 2)
    return CheckResult(
        check_type="fraud",
        status="complete",
        detail={"risk_score": risk_score, "flags": []},
    )
