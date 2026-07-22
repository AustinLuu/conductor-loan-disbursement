from temporalio import activity

from backend.db.models import ReviewTask
from backend.db.session import session_scope
from backend.domain import ReviewTaskInput


@activity.defn
async def create_review_task(input: ReviewTaskInput) -> None:
    async with session_scope() as session:
        session.add(
            ReviewTask(
                application_id=input.application_id,
                reason=input.reason,
                status="pending",
            )
        )
