"""Bounded process metrics and authenticated infrastructure metrics."""
from collections import defaultdict
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy import func
import redis.asyncio as redis

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.audit_log import AgentRun, AgentStep
from app.services.queue import JobQueue

router = APIRouter()
requests = defaultdict(int)
latencies = defaultdict(lambda: [0, 0.0])


def observe(route, method, status, seconds):
    # Route templates bound label cardinality; no UUIDs, query strings or tenant IDs.
    requests[(route, method, status)] += 1
    value = latencies[(route, method)]
    value[0] += 1
    value[1] += seconds


@router.get('/ops/metrics', include_in_schema=False)
async def metrics(authorization: str = Header('')):
    token = settings.OPS_METRICS_TOKEN
    if not token or len(token) < 32:
        raise HTTPException(404, 'Metrics are not configured')
    if not secrets.compare_digest(authorization, 'Bearer ' + token):
        raise HTTPException(401, 'Operator authentication required')
    lines = []
    import json
    for (route, method, code), count in sorted(requests.items()):
        labels = f'route={json.dumps(route)},method={json.dumps(method)},status="{code}"'
        lines.append(f'regulaai_http_requests_total{{{labels}}} {count}')
    for (route, method), (count, total) in sorted(latencies.items()):
        labels = f'route={json.dumps(route)},method={json.dumps(method)}'
        lines.extend([f'regulaai_http_duration_seconds_count{{{labels}}} {count}',
                      f'regulaai_http_duration_seconds_sum{{{labels}}} {total}'])
    queue = JobQueue()
    try:
        await queue.connect()
        client = queue._client
        for state, key in [('ready', queue._queue_name), ('running', queue._processing_queue),
                           ('retrying', queue._delayed_queue), ('failed', queue._dead_letter_queue)]:
            lines.append(f'regulaai_jobs{{state="{state}"}} {await client.zcard(key)}')
        workers = sum([1 async for _ in client.scan_iter(match='regulaai:worker:*', count=100)])
        lines.append(f'regulaai_workers_alive {workers}')
    except Exception:
        lines.append('regulaai_redis_available 0')
    else:
        lines.append('regulaai_redis_available 1')
    finally:
        await queue.disconnect()
    try:
        with SessionLocal() as db:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            groups = db.query(AgentRun.status, func.count(AgentRun.id)).filter(AgentRun.started_at >= since).group_by(AgentRun.status).all()
            for state, count in groups:
                safe_state = state if state in {'running', 'completed', 'failed'} else 'other'
                lines.append(f'regulaai_agent_runs_24h{{state="{safe_state}"}} {count}')
            tokens = db.query(func.sum(AgentStep.token_usage)).filter(AgentStep.started_at >= since).scalar() or 0
            lines.append(f'regulaai_model_tokens_24h {tokens}')
    except Exception:
        lines.append('regulaai_database_available 0')
    else:
        lines.append('regulaai_database_available 1')
    lines.append(f'regulaai_model_execution_enabled {int(settings.MODEL_EXECUTION_ENABLED)}')
    return Response('\n'.join(lines) + '\n', media_type='text/plain; version=0.0.4')
