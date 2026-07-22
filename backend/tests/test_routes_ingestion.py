from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from temporalio.exceptions import WorkflowAlreadyStartedError

from backend import ingestion
from backend.api import routes_applications as routes
from backend.domain import ProductType


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

    # ingest_broker_email persists via backend.ingestion.start_application,
    # which resolves session_scope from its own module (see test_ingestion.py) —
    # patching routes.session_scope here would be a no-op and silently hit
    # the real database.
    monkeypatch.setattr(ingestion, "session_scope", fake_scope)
    return session


def _broker_submission(**overrides):
    defaults = dict(
        message_id="msg-1",
        broker_name="Acme Brokers",
        product_type=ProductType.PERSONAL,
        requested_amount=Decimal("12000"),
        applicant_name="Jane Doe",
        applicant_ssn="123456789",
        submitted_documents=["government_id"],
    )
    defaults.update(overrides)
    return routes.BrokerEmailSubmission(**defaults)


async def test_ingest_broker_email_starts_workflow_and_persists(monkeypatch):
    session = _patch_session_scope(monkeypatch)
    client = SimpleNamespace(start_workflow=AsyncMock())

    result = await routes.ingest_broker_email(_broker_submission(), client=client)

    assert result["workflow_id"] == "loan-app-broker_email-msg-1"
    assert len(session.added) == 1
    assert session.added[0].channel == "broker_email"
    client.start_workflow.assert_awaited_once()


async def test_ingest_broker_email_conflicts_on_duplicate(monkeypatch):
    _patch_session_scope(monkeypatch)
    client = SimpleNamespace(
        start_workflow=AsyncMock(
            side_effect=WorkflowAlreadyStartedError(
                "loan-app-broker_email-msg-1", "LoanApplicationWorkflow"
            )
        )
    )

    with pytest.raises(routes.HTTPException) as exc_info:
        await routes.ingest_broker_email(_broker_submission(), client=client)

    assert exc_info.value.status_code == 409
