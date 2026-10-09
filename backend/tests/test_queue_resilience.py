import asyncio
import json
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.services.queue import JobQueue, Job, JobStatus, JobPriority


@pytest.mark.asyncio
async def test_job_idempotency_key_prevents_duplicate_enqueue():
    queue = JobQueue(redis_url="redis://localhost:6379/14")
    isolate(queue)
    await queue.connect()

    key = f"idem-{uuid4().hex}"
    job1 = Job(
        type="test_idem",
        payload={"param": 1},
        organization_id=str(uuid4()),
        idempotency_key=key,
    )
    job2 = Job(
        type="test_idem",
        payload={"param": 2},
        organization_id=job1.organization_id,
        idempotency_key=key,
    )

    try:
        enqueued1 = await queue.enqueue(job1)
        enqueued2 = await queue.enqueue(job2)

        assert enqueued1.id == enqueued2.id
        assert enqueued2.payload == {"param": 1}
    finally:
        # Cleanup
        if queue._client:
            await cleanup(queue, [value for value in locals().values() if isinstance(value, Job)])
        await queue.disconnect()


@pytest.mark.asyncio
async def test_job_retry_and_terminal_failure_dead_letter():
    queue = JobQueue(redis_url="redis://localhost:6379/14")
    isolate(queue)
    queue.retry_base_seconds = 0
    await queue.connect()

    job = Job(
        type="test_retry",
        payload={"action": "test"},
        organization_id=str(uuid4()),
        max_retries=2,
    )

    try:
        await queue.enqueue(job)
        assert job.status == JobStatus.QUEUED

        # Dequeue
        dequeued = await queue.dequeue(worker_id="w-1", count=1)
        assert len(dequeued) == 1
        active_job = dequeued[0]
        assert active_job.status == JobStatus.RUNNING

        # First failure -> Should retry
        await queue.fail(active_job, "Transient connection failure")
        assert active_job.status == JobStatus.RETRYING
        assert active_job.retry_count == 1

        # Second dequeue and failure -> Should reach max_retries and fail terminally
        dequeued_again = await queue.dequeue(worker_id="w-1", count=1)
        assert len(dequeued_again) == 1
        await queue.fail(dequeued_again[0], "Persistent failure")
        assert dequeued_again[0].status == JobStatus.FAILED
        assert dequeued_again[0].retry_count == 2
        assert dequeued_again[0].finished_at is not None

        # Verify dead letter queue contains the failed job
        dead_count = await queue._client.zcard(queue._dead_letter_queue)
        assert dead_count == 1
    finally:
        if queue._client:
            await cleanup(queue, [value for value in locals().values() if isinstance(value, Job)])
        await queue.disconnect()


@pytest.mark.asyncio
async def test_job_priority_ordering():
    queue = JobQueue(redis_url="redis://localhost:6379/14")
    isolate(queue)
    await queue.connect()

    org_id = str(uuid4())
    job_low = Job(type="p_low", payload={}, organization_id=org_id, priority=JobPriority.LOW)
    job_high = Job(type="p_high", payload={}, organization_id=org_id, priority=JobPriority.HIGH)
    job_critical = Job(type="p_crit", payload={}, organization_id=org_id, priority=JobPriority.CRITICAL)

    try:
        # Enqueue in reverse priority order
        await queue.enqueue(job_low)
        await queue.enqueue(job_high)
        await queue.enqueue(job_critical)

        # Dequeue in batches of 1 and verify order is CRITICAL -> HIGH -> LOW
        batch1 = await queue.dequeue(worker_id="w-priority", count=1)
        batch2 = await queue.dequeue(worker_id="w-priority", count=1)
        batch3 = await queue.dequeue(worker_id="w-priority", count=1)

        assert batch1[0].priority == JobPriority.CRITICAL
        assert batch2[0].priority == JobPriority.HIGH
        assert batch3[0].priority == JobPriority.LOW
    finally:
        if queue._client:
            await cleanup(queue, [value for value in locals().values() if isinstance(value, Job)])
        await queue.disconnect()


def isolate(queue):
    prefix = "regulaai:test:" + uuid4().hex
    queue._queue_name = prefix + ":ready"
    queue._processing_queue = prefix + ":processing"
    queue._delayed_queue = prefix + ":delayed"
    queue._dead_letter_queue = prefix + ":dead"


async def cleanup(queue, jobs):
    import hashlib
    keys = [queue._queue_name, queue._processing_queue, queue._delayed_queue, queue._dead_letter_queue]
    for job in jobs:
        keys.append("job:" + job.id)
        identity = hashlib.sha256(f"{job.organization_id}:{job.type}:{job.idempotency_key or job.id}".encode()).hexdigest()
        keys.append("regulaai:idempotency:" + identity)
    await queue._client.delete(*keys)
