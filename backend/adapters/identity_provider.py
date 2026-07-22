import random

from backend.adapters.mock_support import maybe_fail, simulate_latency
from backend.domain import ApplicationInput, CheckResult


async def verify_identity(application: ApplicationInput) -> CheckResult:
    await simulate_latency()
    maybe_fail("identity_provider")
    confidence = round(random.uniform(0.8, 0.99), 2)
    return CheckResult(
        check_type="identity",
        status="complete",
        detail={"match": True, "confidence": confidence},
    )
