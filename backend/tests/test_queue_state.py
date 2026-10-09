import asyncio
from uuid import uuid4

from app.services.queue import Job, JobQueue
from app.services import queue as queue_module


class RecordingPipeline:
    def __init__(self):
        self.commands = []

    def hset(self, *args, **kwargs):
        self.commands.append(("hset", args, kwargs))
        return self

    def zrem(self, *args):
        self.commands.append(("zrem", args, {}))
        return self

    async def execute(self):
        return []


class RecordingRedis:
    def __init__(self):
        self.last_pipeline = None

    def pipeline(self):
        self.last_pipeline = RecordingPipeline()
        return self.last_pipeline

    async def eval(self, script, count, *args):
        self.eval_call = (script, count, args)
        return 1


def test_completing_job_removes_stable_id_from_processing_queue():
    async def run():
        queue = JobQueue("redis://localhost:6379/15")
        client = RecordingRedis()
        queue._client = client
        job = Job(type="test", payload={}, organization_id=str(uuid4()))

        await queue.complete(job, {"status": "done"})

        script, count, args = client.eval_call
        assert "redis.call('ZREM', KEYS[2], ARGV[1])" in script
        assert count == 3 and args[1] == queue._processing_queue and args[3] == job.id

    asyncio.run(run())


def test_application_queue_is_reused_and_closed_at_shutdown(monkeypatch):
    class ManagedQueue:
        def __init__(self):
            self.connect_count = 0
            self.disconnect_count = 0

        async def connect(self):
            self.connect_count += 1

        async def disconnect(self):
            self.disconnect_count += 1

    async def run():
        managed = ManagedQueue()
        monkeypatch.setattr(queue_module, "_default_queue", None)
        monkeypatch.setattr(queue_module, "JobQueue", lambda: managed)

        first = await queue_module.get_queue()
        second = await queue_module.get_queue()
        assert first is second is managed
        assert managed.connect_count == 2

        await queue_module.close_queue()

        assert managed.disconnect_count == 1
        assert queue_module._default_queue is None

    asyncio.run(run())
