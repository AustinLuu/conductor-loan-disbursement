"""Shared simulated latency/failure behavior for the mocked third-party
adapters (system design §3.3). Not in the TDD's file list as its own module,
but every adapter needs the same two behaviors, so it's factored out once
rather than copy-pasted four times.

Both knobs default to "off" so a fresh `docker-compose up` demo run is
deterministic; set the env vars to exercise retry/backoff behavior.
"""
import asyncio
import os
import random

from temporalio.exceptions import ApplicationError


async def simulate_latency() -> None:
    seconds = float(os.environ.get("MOCK_LATENCY_SECONDS", "0.05"))
    await asyncio.sleep(seconds)


def maybe_fail(provider: str) -> None:
    rate = float(os.environ.get("MOCK_FAILURE_RATE", "0.0"))
    if random.random() < rate:
        raise ApplicationError(
            f"{provider} temporarily unavailable (simulated)",
            type="ProviderUnavailableError",
            non_retryable=False,
        )
