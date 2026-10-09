import asyncio
import signal
import sys
import platform
import os
from uuid import uuid4

from app.core.config import settings
from app.services.queue import JobQueue, Worker
from app.workers.handlers import get_handlers


async def main():
    queue = JobQueue()
    await queue.connect()

    handlers = get_handlers()

    worker = Worker(
        queue=queue,
        worker_id=f"regulaai-worker-{settings.ENVIRONMENT}-{platform.node()}-{os.getpid()}-{uuid4().hex[:8]}",
        handlers=handlers,
        poll_interval=1.0,
        max_concurrent=5,
    )

    loop = asyncio.get_running_loop()

    def shutdown():
        print("Shutdown signal received...")
        asyncio.create_task(worker.stop())

    # Add signal handlers only on Unix (not Windows)
    if platform.system() != "Windows":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown)
    else:
        # On Windows, we'll handle Ctrl+C via KeyboardInterrupt
        pass

    print(f"Starting worker: {worker.worker_id}")
    await worker.start()

    try:
        while worker._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("Keyboard interrupt received...")
        await worker.stop()
    finally:
        await worker.stop()
        print("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
