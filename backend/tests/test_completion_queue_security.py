import asyncio
import copy
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from app.services.queue import Job, JobQueue, Worker, JobStatus
from test_queue_resilience import isolate, cleanup


@pytest.mark.asyncio
async def test_atomic_idempotency_is_tenant_scoped_under_concurrency():
    queue = JobQueue('redis://localhost:6379/14')
    isolate(queue)
    jobs = [Job(type='atomic_test', organization_id=str(uuid4()), payload={}, idempotency_key='same')]
    jobs.extend(Job(type='atomic_test', organization_id=jobs[0].organization_id, payload={}, idempotency_key='same') for _ in range(9))
    jobs.append(Job(type='atomic_test', organization_id=str(uuid4()), payload={}, idempotency_key='same'))
    try:
        results = await asyncio.gather(*(queue.enqueue(job) for job in jobs))
        assert len({job.id for job in results[:10]}) == 1
        assert results[-1].id != results[0].id
        assert await queue._client.zcard(queue._queue_name) == 2
    finally:
        await cleanup(queue, jobs)
        await queue.disconnect()


@pytest.mark.asyncio
async def test_backoff_and_expired_lease_ignore_late_completion():
    queue = JobQueue('redis://localhost:6379/14')
    isolate(queue)
    job = Job(type='lease', payload={}, organization_id=str(uuid4()))
    try:
        await queue.enqueue(job)
        running = (await queue.dequeue('old-worker'))[0]
        stale = copy.deepcopy(running)
        await queue.fail(running, 'Safe transient failure')
        saved = await queue.get_job(job.id)
        assert saved.status == JobStatus.RETRYING
        assert (saved.next_retry_at - saved.updated_at).total_seconds() >= 2
        assert await queue.dequeue('next-worker') == []
        await queue.complete(stale, {'late': True})
        assert (await queue.get_job(job.id)).status == JobStatus.RETRYING
        await asyncio.sleep(2.1)
        running = (await queue.dequeue('next-worker'))[0]
        await queue._client.zadd(queue._processing_queue, {job.id: 0})
        await queue.recover_expired()
        assert (await queue.get_job(job.id)).retry_count == 2
    finally:
        await cleanup(queue, [job])
        await queue._client.delete(f'regulaai:recover:{job.id}')
        await queue.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['semantic_failure', 'timeout'])
async def test_worker_semantic_failure_and_timeout_fail_safely(monkeypatch, kind):
    from app.services import execution
    async def execute(handler, job):
        return await handler.handle(job)
    monkeypatch.setattr(execution, 'execute_job', execute)
    class Handler:
        async def handle(self, job):
            if kind == 'timeout':
                await asyncio.sleep(10)
            return {'status': 'failed', 'error': 'Private source must not be propagated'}
    queue = JobQueue('redis://localhost:6379/14')
    isolate(queue)
    job = Job(type=kind, payload={}, organization_id=str(uuid4()), max_retries=1, timeout_seconds=1)
    try:
        await queue.enqueue(job)
        running = (await queue.dequeue('test-worker'))[0]
        await Worker(queue, 'test-worker', {kind: Handler()})._process_job(running)
        saved = await queue.get_job(job.id)
        assert saved.status == JobStatus.FAILED
        assert saved.result is None
        assert 'Private source' not in saved.error
        assert await queue._client.zscore(queue._processing_queue, job.id) is None
    finally:
        await cleanup(queue, [job])
        await queue.disconnect()
