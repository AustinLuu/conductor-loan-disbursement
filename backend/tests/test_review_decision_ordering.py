from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api import routes_applications as routes


class _FakeSession:
    def __init__(self, review_task, application):
        self._objects = {"review": review_task, "app": application}

    async def get(self, model, id_):
        if model.__name__ == "ReviewTask":
            return self._objects["review"]
        return self._objects["app"]


def _patch_session_scope(monkeypatch, review_task, application):
    @asynccontextmanager
    async def fake_scope():
        yield _FakeSession(review_task, application)

    monkeypatch.setattr(routes, "session_scope", fake_scope)


async def test_review_stays_pending_when_signal_fails(monkeypatch):
    review_task = SimpleNamespace(status="pending", decision=None, notes="", application_id="app-1")
    application = SimpleNamespace(workflow_id="wf-1")
    _patch_session_scope(monkeypatch, review_task, application)

    handle = SimpleNamespace(signal=AsyncMock(side_effect=RuntimeError("temporal down")))
    client = SimpleNamespace(get_workflow_handle=lambda wf_id: handle)

    submission = routes.ReviewDecisionSubmission(
        outcome="approve", reason="ok", reviewer="alice"
    )

    with pytest.raises(RuntimeError):
        await routes.submit_review_decision("review-1", submission, client=client)

    assert review_task.status == "pending"


async def test_review_marked_decided_after_successful_signal(monkeypatch):
    review_task = SimpleNamespace(status="pending", decision=None, notes="", application_id="app-1")
    application = SimpleNamespace(workflow_id="wf-1")
    _patch_session_scope(monkeypatch, review_task, application)

    handle = SimpleNamespace(signal=AsyncMock())
    client = SimpleNamespace(get_workflow_handle=lambda wf_id: handle)

    submission = routes.ReviewDecisionSubmission(
        outcome="approve", reason="ok", reviewer="alice"
    )

    result = await routes.submit_review_decision("review-1", submission, client=client)

    assert result == {"status": "signaled"}
    assert review_task.status == "decided"
    assert review_task.decision == "approve"
