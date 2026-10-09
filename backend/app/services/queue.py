import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import UUID
import asyncio
import os

import redis.asyncio as redis
from pydantic import BaseModel, Field

from app.core.config import settings


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class JobPriority(int, Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    payload: Dict[str, Any]
    organization_id: str
    user_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    workflow_id: Optional[str] = None
    step_order: int = 0
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    next_retry_at: Optional[datetime] = None
    worker_id: Optional[str] = None

    def to_dict(self) -> dict:
        data = self.model_dump(mode="json")
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.finished_at:
            data["finished_at"] = self.finished_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        data = data.copy()
        data["status"] = JobStatus(data["status"])
        data["priority"] = JobPriority(data["priority"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("finished_at"):
            data["finished_at"] = datetime.fromisoformat(data["finished_at"])
        return cls(**data)


class JobQueue:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._client: Optional[redis.Redis] = None
        prefix = os.getenv("JOB_QUEUE_PREFIX", "regulaai:jobs")
        self._queue_name = prefix
        self._processing_queue = prefix + ":processing"
        self._dead_letter_queue = prefix + ":dead"
        self._delayed_queue = prefix + ":delayed"
        self.retry_base_seconds = 2

    async def connect(self):
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def enqueue(self, job: Job) -> Job:
        await self.connect()
        job.status = JobStatus.QUEUED
        job.updated_at = datetime.now(timezone.utc)
        # The tenant is part of every idempotency identity. Lua reserves and
        # enqueues atomically, preventing concurrent requests from duplicating work.
        import hashlib
        identity = hashlib.sha256(f"{job.organization_id}:{job.type}:{job.idempotency_key or job.id}".encode()).hexdigest()
        existing_id = await self._client.eval("""
            local existing = redis.call('GET', KEYS[1])
            if existing and redis.call('EXISTS', 'job:' .. existing) == 1 then return existing end
            redis.call('SET', KEYS[1], ARGV[1], 'EX', 86400)
            redis.call('HSET', KEYS[2], 'data', ARGV[2])
            redis.call('EXPIRE', KEYS[2], 604800)
            redis.call('ZADD', KEYS[3], ARGV[3], ARGV[2])
            return ARGV[1]
        """, 3, f"regulaai:idempotency:{identity}", f"job:{job.id}", self._queue_name,
            job.id, json.dumps(job.to_dict()), -job.priority.value)
        return await self.get_job(existing_id)

    async def recover_expired(self):
        await self.connect()
        now = datetime.now(timezone.utc).timestamp()
        # Promote delayed retries with a single atomic operation.
        await self._client.eval("""
            local due = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
            for _, data in ipairs(due) do
                local job = cjson.decode(data)
                redis.call('ZADD', KEYS[2], -job.priority, data)
                redis.call('ZREM', KEYS[1], data)
            end
            return #due
        """, 2, self._delayed_queue, self._queue_name, now)
        expired = await self._client.zrangebyscore(self._processing_queue, '-inf', now)
        for job_id in expired:
            # Acquire a recovery lock; stale lease entries cannot spawn two retries.
            if await self._client.set(f"regulaai:recover:{job_id}", "1", nx=True, ex=30):
                job = await self.get_job(job_id)
                if job and job.status == JobStatus.RUNNING:
                    await self.fail(job, "Worker lease expired")
                else:
                    await self._client.zrem(self._processing_queue, job_id)

    async def dequeue(self, worker_id: str, count: int = 1) -> list[Job]:
        await self.connect()
        await self.recover_expired()
        jobs = []
        for _ in range(count):
            now = datetime.now(timezone.utc)
            data = await self._client.eval("""
                local item = redis.call('ZPOPMIN', KEYS[1], 1)
                if #item == 0 then return nil end
                local job = cjson.decode(item[1])
                job.status = 'running'
                job.started_at = ARGV[1]
                job.updated_at = ARGV[1]
                job.worker_id = ARGV[3]
                local encoded = cjson.encode(job)
                redis.call('HSET', 'job:' .. job.id, 'data', encoded)
                redis.call('ZADD', KEYS[2], tonumber(ARGV[2]) + (job.timeout_seconds or 300) + 30, job.id)
                return encoded
            """, 2, self._queue_name, self._processing_queue, now.isoformat(), now.timestamp(), worker_id)
            if not data:
                break
            jobs.append(Job.from_dict(json.loads(data)))
        return jobs

    async def complete(self, job: Job, result: Optional[Dict[str, Any]] = None):
        await self.connect()

        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(timezone.utc)
        job.updated_at = job.finished_at
        job.result = result

        await self._finish(job)

    async def _finish(self, job: Job, destination=None, score=0):
        """Only the current lease owner may publish a terminal/retry state."""
        return await self._client.eval("""
            local raw = redis.call('HGET', KEYS[1], 'data')
            if ARGV[3] ~= '' then
                if not raw then return 0 end
                local previous = cjson.decode(raw)
                if previous.status ~= 'running' or previous.worker_id ~= ARGV[3] or previous.started_at ~= ARGV[4] then return 0 end
            end
            redis.call('HSET', KEYS[1], 'data', ARGV[2])
            redis.call('EXPIRE', KEYS[1], 604800)
            redis.call('ZREM', KEYS[2], ARGV[1])
            if ARGV[5] ~= '' then redis.call('ZADD', KEYS[3], ARGV[6], ARGV[2]) end
            return 1
        """, 3, f"job:{job.id}", self._processing_queue, destination or self._dead_letter_queue,
            job.id, json.dumps(job.to_dict()), job.worker_id or '', job.started_at.isoformat() if job.started_at else '',
            destination or '', score)

    async def fail(self, job: Job, error: str):
        await self.connect()

        job.retry_count += 1
        job.error = error
        job.updated_at = datetime.now(timezone.utc)

        if job.retry_count < job.max_retries:
            job.status = JobStatus.RETRYING
            delay = self.retry_base_seconds * (2 ** (job.retry_count - 1))
            job.next_retry_at = datetime.fromtimestamp(job.updated_at.timestamp() + delay, timezone.utc)
            await self._finish(job, self._delayed_queue, job.next_retry_at.timestamp())
        else:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc)

            await self._finish(job, self._dead_letter_queue, job.finished_at.timestamp())

    async def get_job(self, job_id: str) -> Optional[Job]:
        await self.connect()
        data = await self._client.hget(f"job:{job_id}", "data")
        if data:
            return Job.from_dict(json.loads(data))
        return None

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        job = await self.get_job(job_id)
        return job.status if job else None


class JobHandler(ABC):
    @abstractmethod
    async def handle(self, job: Job) -> Dict[str, Any]:
        pass


class Worker:
    def __init__(
        self,
        queue: JobQueue,
        worker_id: str,
        handlers: Dict[str, JobHandler],
        poll_interval: float = 1.0,
        max_concurrent: int = 5,
    ):
        self.queue = queue
        self.worker_id = worker_id
        self.handlers = handlers
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._heartbeat_at = 0

    async def start(self):
        self._running = True
        await self.queue.connect()
        self._poll_task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        poll = getattr(self, "_poll_task", None)
        if poll:
            poll.cancel()
            await asyncio.gather(poll, return_exceptions=True)
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.queue.disconnect()

    async def _run(self):
        while self._running:
            try:
                if asyncio.get_running_loop().time() - self._heartbeat_at > 15:
                    await self.queue._client.set(f"regulaai:worker:{self.worker_id}", json.dumps({"worker_id": self.worker_id,
                        "active_jobs": len(self._tasks), "capacity": self.max_concurrent,
                        "at": datetime.now(timezone.utc).isoformat()}), ex=60)
                    self._heartbeat_at = asyncio.get_running_loop().time()
                if len(self._tasks) < self.max_concurrent:
                    jobs = await self.queue.dequeue(self.worker_id, count=1)
                    if not jobs:
                        await asyncio.sleep(self.poll_interval)
                    for job in jobs:
                        task = asyncio.create_task(self._process_job(job))
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)
                else:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    "Worker poll loop failed",
                    extra={"worker_id": self.worker_id, "error_type": type(e).__name__},
                )
                await asyncio.sleep(self.poll_interval)

    async def _process_job(self, job: Job):
        handler = self.handlers.get(job.type)
        if not handler:
            await self.queue.fail(job, f"No handler for job type: {job.type}")
            return

        try:
            from app.services.execution import execute_job
            result = await asyncio.wait_for(execute_job(handler, job), timeout=job.timeout_seconds)
            if result.get("status") in {"failed", "error"}:
                raise RuntimeError("Agent reported failure")
            await self.queue.complete(job, result)
        except asyncio.CancelledError:
            await asyncio.shield(self.queue.fail(job, "Worker stopped during execution"))
            raise
        except Exception as e:
            # Exception strings can embed SQL URLs, prompt text, or document content.
            await self.queue.fail(job, f"Handler failed ({type(e).__name__})")


T = TypeVar("T", bound=BaseModel)


def create_job(
    job_type: str,
    payload: Dict[str, Any],
    organization_id: UUID,
    user_id: Optional[UUID] = None,
    priority: JobPriority = JobPriority.NORMAL,
    max_retries: int = 3,
    idempotency_key: Optional[str] = None,
    workflow_id: Optional[str] = None,
    step_order: int = 0,
) -> Job:
    return Job(
        type=job_type,
        payload=payload,
        organization_id=str(organization_id),
        user_id=str(user_id) if user_id else None,
        priority=priority,
        max_retries=max_retries,
        idempotency_key=idempotency_key,
        workflow_id=workflow_id,
        step_order=step_order,
    )


async def get_queue() -> JobQueue:
    global _default_queue
    if _default_queue is None:
        _default_queue = JobQueue()
    await _default_queue.connect()
    return _default_queue


_default_queue: Optional[JobQueue] = None


async def close_queue() -> None:
    global _default_queue
    if _default_queue is not None:
        queue, _default_queue = _default_queue, None
        await queue.disconnect()
