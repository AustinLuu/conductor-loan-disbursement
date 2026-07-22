from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import AsyncMock

from temporalio.exceptions import WorkflowAlreadyStartedError

from backend import ingestion
from backend.domain import Channel, ProductType


class _FakeSession:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


def _patch_session_scope(monkeypatch):
    session = _FakeSession()

    @asynccontextmanager
    async def fake_scope():
        yield session

    monkeypatch.setattr(ingestion, "session_scope", fake_scope)
    return session


async def test_start_application_accepted_starts_workflow_and_persists(monkeypatch):
    session = _patch_session_scope(monkeypatch)
    client = AsyncMock()

    outcome = await ingestion.start_application(
        client,
        channel=Channel.BROKER_EMAIL,
        external_ref="msg-1",
        product_type=ProductType.PERSONAL,
        requested_amount=Decimal("5000"),
        applicant_name="Jane Doe",
        applicant_ssn="123456789",
        submitted_documents=["government_id"],
    )

    assert outcome.status == "accepted"
    assert outcome.workflow_id == "loan-app-broker_email-msg-1"
    assert outcome.application_id is not None
    assert len(session.added) == 1
    persisted = session.added[0]
    assert persisted.channel == "broker_email"
    assert persisted.external_ref == "msg-1"
    assert persisted.applicant_ssn_last4 == "6789"
    client.start_workflow.assert_awaited_once()


async def test_start_application_duplicate_does_not_persist(monkeypatch):
    session = _patch_session_scope(monkeypatch)
    client = AsyncMock()
    client.start_workflow.side_effect = WorkflowAlreadyStartedError(
        "loan-app-portal-ext-1", "LoanApplicationWorkflow"
    )

    outcome = await ingestion.start_application(
        client,
        channel=Channel.PORTAL,
        external_ref="ext-1",
        product_type=ProductType.PERSONAL,
        requested_amount=Decimal("5000"),
        applicant_name="Jane Doe",
        applicant_ssn="123456789",
        submitted_documents=[],
    )

    assert outcome.status == "duplicate"
    assert outcome.application_id is None
    assert session.added == []
