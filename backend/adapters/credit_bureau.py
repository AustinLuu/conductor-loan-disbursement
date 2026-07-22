import random

from backend.adapters.mock_support import maybe_fail, simulate_latency
from backend.domain import ApplicationInput, CheckResult


async def fetch_credit_report(application: ApplicationInput) -> CheckResult:
    await simulate_latency()
    maybe_fail("credit_bureau")
    score = random.randint(560, 800)
    return CheckResult(
        check_type="credit",
        status="complete",
        detail={"score": score, "tradelines": random.randint(2, 8)},
    )
