import asyncio
from uuid import uuid4

from app.services.queue import Job, Worker


class FailingQueue:
    def __init__(self):
        self.error = None

    async def fail(self, _job, error):
        self.error = error

    async def complete(self, _job, _result):
        raise AssertionError("A failed handler must not be marked complete")


class FailingHandler:
    async def handle(self, _job):
        raise RuntimeError("database password=do-not-log or confidential document text")


def test_worker_does_not_persist_raw_exception_text(monkeypatch):
    async def execute(handler, job):
        return await handler.handle(job)
    monkeypatch.setattr("app.services.execution.execute_job", execute)
    queue = FailingQueue()
    worker = Worker(queue, "test-worker", {"test": FailingHandler()})
    job = Job(type="test", payload={}, organization_id=str(uuid4()))

    asyncio.run(worker._process_job(job))

    assert queue.error == "Handler failed (RuntimeError)"
    assert "password" not in queue.error
    assert "confidential" not in queue.error
