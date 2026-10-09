"""Bounded HTTP + actual parser-worker load; no paid models or cloud services."""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db.session import SessionLocal
from app.db import base
from app.core.security import create_access_token, get_password_hash
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.regulation import RegulatoryDocument, RegulatoryVersion
from app.services.queue import JobQueue, create_job


async def main():
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if settings.ENVIRONMENT != 'test' or url.host not in {'localhost', '127.0.0.1'} or not url.database.startswith('regulaai_verify_'):
        raise RuntimeError('Only a disposable local verification database is accepted')
    run = uuid4().hex[:12]
    os.environ['JOB_QUEUE_PREFIX'] = f'regulaai:load:{run}'
    output = Path('../output/load'); output.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        user = User(email=f'load-{run}@example.test', full_name='Synthetic Load Reviewer', hashed_password=get_password_hash(uuid4().hex))
        org = Organization(name=f'Synthetic Load Bank {run}')
        db.add_all([user, org]); db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role='Owner'))
        doc = RegulatoryDocument(organization_id=org.id, title='Synthetic load fixture', document_type='synthetic', status='uploaded')
        db.add(doc); db.flush()
        versions = [RegulatoryVersion(document_id=doc.id, version_number=i+1, status='uploaded', raw_text='The synthetic bank shall review capital daily. '*50) for i in range(20)]
        db.add_all(versions); db.commit()
        user_id, org_id = user.id, org.id
        version_ids = [v.id for v in versions]
    env = dict(os.environ)
    env['ALLOWED_HOSTS'] = '["localhost","127.0.0.1"]'
    log = (output/'service.log').open('w', encoding='utf-8')
    api = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8020'], env=env, stdout=log, stderr=log)
    worker = subprocess.Popen([sys.executable, '-m', 'app.workers.main'], env=env, stdout=log, stderr=log)
    queue = JobQueue()
    jobs = []
    try:
        async with httpx.AsyncClient(base_url='http://127.0.0.1:8020', headers={'Authorization': 'Bearer '+create_access_token(str(user_id))}, timeout=20) as client:
            for _ in range(50):
                try:
                    if (await client.get('/api/health/live')).status_code == 200: break
                except httpx.ConnectError: pass
                await asyncio.sleep(.2)
            else: raise RuntimeError('Load API did not start')
            semaphore = asyncio.Semaphore(10)
            async def sample(index):
                async with semaphore:
                    started = time.monotonic()
                    response = await client.get(f'/api/evaluation/demo/compliance-matrix?organization_id={org_id}')
                    return (time.monotonic()-started)*1000, response.status_code
            warmup = await asyncio.gather(*(sample(i) for i in range(20)))
            began = time.monotonic()
            samples = await asyncio.gather(*(sample(i) for i in range(100)))
            http_elapsed = time.monotonic()-began
            began = time.monotonic()
            for version_id in version_ids:
                jobs.append(await queue.enqueue(create_job('regulation_process', {'version_id': str(version_id)}, org_id, user_id)))
            for _ in range(120):
                saved = [await queue.get_job(job.id) for job in jobs]
                if all(j.status.value in {'succeeded', 'failed'} for j in saved): break
                await asyncio.sleep(.5)
            latencies = sorted(t for t, status in samples)
            completed = sum(j.status.value == 'succeeded' for j in saved)
            elapsed = time.monotonic()-began
            report = {'scope': 'local HTTP read load against empty tenant matrix plus 20 actual parser-worker jobs; no external model',
                'requests': 100, 'warmup_requests': 20, 'concurrency': 10, 'http_errors': sum(status != 200 for _, status in samples),
                'http_elapsed_seconds': round(http_elapsed, 3), 'requests_per_second': round(100/http_elapsed, 2),
                'latency_ms': {name: round(latencies[min(len(latencies)-1, int(percent*len(latencies)))], 2) for name,percent in [('p50', .5), ('p95', .95), ('p99', .99)]},
                'jobs_submitted': 20, 'jobs_succeeded': completed, 'worker_elapsed_seconds': round(elapsed, 3),
                'jobs_per_second': round(completed/elapsed, 2),
                'queue_lag_seconds_max': round(max((j.started_at-j.created_at).total_seconds() for j in saved if j.started_at), 3),
                'status': 'passed' if completed == 20 and all(status == 200 for _,status in samples) else 'failed',
                'limitations': ['No large-tenant query capacity, model latency/cost, cloud resource limits, or staging performance claim.']}
            (output/'load-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
            assert report['status'] == 'passed'
    finally:
        api.terminate(); worker.terminate()
        for process in [api, worker]:
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        await queue.disconnect()
        log.close()


if __name__ == '__main__':
    asyncio.run(main())
