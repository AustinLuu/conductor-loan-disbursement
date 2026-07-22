from decimal import Decimal

import pytest
from unittest.mock import AsyncMock

from backend.activities import batch_ingestion
from backend.domain import BatchApplicationRecord, Channel, ProductType
from backend.ingestion import IngestOutcome


def _record(**overrides):
    defaults = dict(
        external_ref="rec-1",
        product_type=ProductType.PERSONAL,
        requested_amount=Decimal("10000"),
        applicant_name="Jane Doe",
        applicant_ssn="123456789",
        submitted_documents=["government_id"],
    )
    defaults.update(overrides)
    return BatchApplicationRecord(**defaults)


async def test_start_application_workflow_maps_outcome_to_batch_result(monkeypatch):
    fake_outcome = IngestOutcome(
        external_ref="rec-1", status="accepted", application_id="app-1", workflow_id="wf-1"
    )
    mock_start = AsyncMock(return_value=fake_outcome)
    monkeypatch.setattr(batch_ingestion, "start_application", mock_start)
    monkeypatch.setattr(batch_ingestion, "_client", object())

    result = await batch_ingestion.start_application_workflow(_record())

    assert result.external_ref == "rec-1"
    assert result.status == "accepted"
    assert result.application_id == "app-1"
    assert result.workflow_id == "wf-1"
    mock_start.assert_awaited_once()
    _, kwargs = mock_start.call_args
    assert kwargs["channel"] == Channel.AGGREGATOR_BATCH
    assert kwargs["external_ref"] == "rec-1"


async def test_start_application_workflow_requires_configured_client(monkeypatch):
    monkeypatch.setattr(batch_ingestion, "_client", None)

    with pytest.raises(AssertionError, match="configure_client"):
        await batch_ingestion.start_application_workflow(_record())
