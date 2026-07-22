from sqlalchemy import select
from temporalio import activity

from backend.db.models import Document
from backend.db.session import session_scope
from backend.domain import DocumentStatusInput


@activity.defn
async def record_document_status(input: DocumentStatusInput) -> None:
    async with session_scope() as session:
        existing = await session.scalar(
            select(Document).where(
                Document.application_id == input.application_id,
                Document.doc_type == input.doc_type,
            )
        )
        if existing:
            existing.status = input.status
            if input.storage_ref:
                existing.storage_ref = input.storage_ref
        else:
            session.add(
                Document(
                    application_id=input.application_id,
                    doc_type=input.doc_type,
                    status=input.status,
                    storage_ref=input.storage_ref,
                )
            )
