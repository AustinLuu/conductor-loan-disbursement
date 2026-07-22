from datetime import datetime, timezone

from temporalio import activity

from backend.db.models import Application, AuditEvent
from backend.db.session import session_scope
from backend.domain import AuditEventInput


@activity.defn
async def record_audit_event(input: AuditEventInput) -> None:
    """Writes the audit trail row and, when given, advances the Application's
    status — the mechanism behind system design §4.4 (dashboard reads
    Postgres; Temporal owns the process, Postgres owns the data)."""
    async with session_scope() as session:
        session.add(
            AuditEvent(
                application_id=input.application_id,
                event_type=input.event_type,
                actor=input.actor,
                detail=input.detail,
                occurred_at=datetime.now(timezone.utc),
            )
        )
        if input.new_status is not None:
            application = await session.get(Application, input.application_id)
            if application is not None:
                application.status = input.new_status.value
