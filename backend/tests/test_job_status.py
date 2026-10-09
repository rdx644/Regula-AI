from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.endpoints import jobs


def test_job_status_hides_jobs_belonging_to_another_tenant(monkeypatch):
    organization_id = uuid4()
    other_organization_id = uuid4()
    job = SimpleNamespace(
        id="job-123",
        type="regulation_process",
        status=SimpleNamespace(value="succeeded"),
        result={"status": "parsed"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        organization_id=str(other_organization_id),
    )

    class Queue:
        async def get_job(self, _job_id):
            return job

    class Db:
        pass

    async def queue_factory():
        return Queue()

    monkeypatch.setattr(jobs, "get_queue", queue_factory)
    monkeypatch.setattr(jobs.deps, "verify_membership", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        import asyncio
        asyncio.run(jobs.get_job_status(
            job_id="job-123",
            organization_id=organization_id,
            db=Db(),
            current_user=SimpleNamespace(id=uuid4()),
        ))

    assert exc_info.value.status_code == 404
