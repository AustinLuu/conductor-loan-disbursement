from sqlalchemy import select
from temporalio import activity

from backend.adapters import core_banking
from backend.db.models import Check
from backend.db.session import session_scope
from backend.domain import DisburseInput, DisbursementResult


@activity.defn
async def disburse_funds(input: DisburseInput) -> DisbursementResult:
    async with session_scope() as session:
        existing = await session.scalar(
            select(Check).where(
                Check.application_id == input.application_id,
                Check.check_type == "disbursement",
                Check.status == "complete",
            )
        )
        if existing:
            return DisbursementResult(**existing.result)

    confirmation_id = await core_banking.disburse(input.idempotency_key, input.amount)
    result = DisbursementResult(
        confirmation_id=confirmation_id, idempotency_key=input.idempotency_key
    )

    async with session_scope() as session:
        session.add(
            Check(
                application_id=input.application_id,
                check_type="disbursement",
                status="complete",
                result=result.model_dump(),
                attempt_count=activity.info().attempt,
            )
        )
    return result
