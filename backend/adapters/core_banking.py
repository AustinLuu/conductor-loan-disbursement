"""Mocked core banking disbursement API — the one call in this pipeline
where blind retry is unsafe (system design §6, 'Exactly-once disbursement').
Keyed by idempotency_key, so a redelivered request returns the original
confirmation instead of moving money twice."""
from decimal import Decimal

from backend.adapters.mock_support import maybe_fail, simulate_latency

_CONFIRMED: dict[str, str] = {}


async def disburse(idempotency_key: str, amount: Decimal) -> str:
    if idempotency_key in _CONFIRMED:
        return _CONFIRMED[idempotency_key]
    await simulate_latency()
    maybe_fail("core_banking")
    confirmation_id = f"conf-{idempotency_key}"
    _CONFIRMED[idempotency_key] = confirmation_id
    return confirmation_id
