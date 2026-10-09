# Deployment and operations handoff

Date: 2026-10-10. The owner authorized preparing the Render blueprint and pushing required files to GitHub, and explicitly reserved approval of plans and secrets for the Render Dashboard. See [Render setup](RENDER_DEPLOYMENT.md). Staging and production remain **unverified**: no Render workspace access, managed storage credentials, recovery objectives or paid-resource approval have been supplied to this session. No resources were provisioned or deployed.

## Release topology

Use `backend/Dockerfile`, `frontend/Dockerfile` and `compose.release.yaml` as a provider-neutral template. The API and worker share PostgreSQL/pgvector, Redis and private S3 storage. The web application and API must share a site through a TLS ingress; route `/api` to FastAPI. The template binds published ports to loopback. Production storage cannot use local disk. Images use non-root users and the API/worker have a read-only filesystem and bounded temporary space.

Container builds were attempted locally. Docker Hub authentication returned HTTP 500/504 while fetching base images, so neither release image has been verified. Retry the documented builds when the registry is available; record immutable image digests before a release.

## Configuration and identity

Inject these **names** through the platform secret manager: `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`, `REDIS_URL`, `OPENAI_API_KEY` only after spending/data approval, `OPS_METRICS_TOKEN`. Do not check runtime environment files into Git.

Set `ENVIRONMENT`, `ALLOWED_HOSTS`, `BACKEND_CORS_ORIGINS`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ENABLE_RATE_LIMITING`, `STORAGE_BACKEND=s3`, `S3_BUCKET`, `AWS_REGION`, optional `S3_ENDPOINT_URL`, and `MAX_UPLOAD_BYTES`. Set `HEALTHCHECK_HOST` to an allowed API hostname for the release healthcheck. Build the frontend with `NEXT_PUBLIC_API_URL=/api` behind same-site ingress. It is a public URL, never a credential.

`MODEL_EXECUTION_ENABLED=false` is the current default and owner instruction. Credentials alone do not enable model calls. `AI_REQUESTS_PER_TENANT_PER_DAY` and `AI_TOKENS_PER_TENANT_PER_DAY` reserve request/token budgets atomically before each provider attempt. Failed attempts consume their reservations. These are conservative token reservations, not a dollar budget; enforce a provider account spending limit as well. Approval of a provider does not authorize sending bank documents to it.

Use separate migration, API, worker, backup and monitoring identities. The migration identity owns schema changes; application identities need only their table/sequence privileges. Use TLS for database and Redis connections when traffic crosses the host boundary. Configure Redis authentication and eviction so durable job keys are preserved. Document connection-pool and database limits per replica before scaling.

The container currently disables proxy-header trust. The ingress address and trusted forwarding configuration must be validated for the chosen target. Otherwise rate limits group users under the ingress IP. Never trust arbitrary forwarded headers. Apply the body-size limit at the edge as well as in the API.

## Private object storage

Require block-public-access (all four settings), versioning, and server-side encryption. The S3 readiness check verifies these settings; uploads request AES256 encryption. Tenant keys contain a category, organization UUID, resource UUID and random object name. Downloads authenticate and authorize the owning organization. There are no public source URLs.

Grant only required object actions and configuration read actions on the configured bucket/prefix. Disallow public ACLs and insecure transport. A local HTTP S3 emulator test verified private encrypted/versioned configuration, upload/read/delete and version recovery. Cloud IAM, lifecycle, KMS, retention, legal holds and public-access posture remain unverified. The owner must approve retention and deletion requirements before irreversible lifecycle rules are applied.

## Release, migrations and rollback

1. Obtain an approved staging account and managed credentials; build and scan images, then record their digests and source revision.
2. Take encrypted database and object snapshots. Verify recoverability before any schema operation on an established environment.
3. Run `python -m alembic upgrade head` with the migration identity. Run `python -m alembic current` and `python -m alembic check` using the same release code.
4. Start the API and worker; confirm `/api/health/live` and `/api/health`. Production readiness requires database, Redis, private storage and a fresh worker heartbeat.
5. Start the web service and perform synthetic cookie/CSRF, tenant-denial, upload/download, queue, failed-job and review smoke checks through TLS.
6. Verify metrics/alerts and an isolated restore. Obtain final production release approval before production deployment.

For application rollback, drain new jobs, wait for active leases, and restore the previous reviewed image digest. Check schema compatibility before rollback. The added migrations are additive; do not automatically downgrade or drop columns. A data restore is a separately approved operation. Rollback has not been exercised in staging.

## Monitoring and alerts

Structured request logs contain method, route template, status, duration and validated request ID. Job/agent traces contain tenant/actor/job IDs, attempt, model/schema/prompt digest and usage. Source text, tokens and credentials must not enter logs or exported telemetry. SDK/SQL debug logs are disabled; exception formatting omits stacks. Audit rows retain approval transitions and identifiers.

`GET /api/ops/metrics` returns Prometheus text only with the separate managed `OPS_METRICS_TOKEN` (at least 32 characters). It returns 404 when disabled and 401 for an invalid credential. Metrics include process request counts/duration sums, ready/running/retrying/dead queue counts, worker heartbeats, recent agent runs, recorded model tokens, service availability and the model switch. Scrape every API replica; request counters are per process. Token metrics represent successfully recorded usage, not invoice reconciliation or failed-call billing.

`docs/operations/alerts.yml` contains proposed thresholds. Provision the monitoring system, import alerts and test actual delivery to an owner-approved destination in staging. No notifications have been sent. Host memory/CPU, database saturation, oldest queue age, latency histograms and provider invoices need target-specific instrumentation. No production dashboard/alert delivery is claimed.

## Failure and incident procedures

| Symptom | Action |
|---|---|
| Readiness 503 | Check component status; compare recent deployment and credential changes. Do not bypass a failed private-bucket check. |
| Missing worker | Check worker process, Redis connectivity and heartbeat expiry; restart the owned worker and observe lease recovery. |
| Job terminal failure | Authorized tenant user reads the safe job result; inspect correlated trace IDs. Correct the input/service cause, then use `/api/jobs/{id}/retry?organization_id=...`. Retry creates a new job and audit record. |
| Queue retries rising | Check dependency availability and timeouts. Limit new work; avoid repeated manual retries. Backoff and lease recovery are automatic. |
| Model quota exhausted | Keep execution disabled or within the approved budget; investigate tenant reservations and provider accounting. Do not raise limits without budget approval. |
| Suspected tenant disclosure | Disable affected routes/model execution, restrict ingress, preserve redacted audit records, and involve the security/data owner. Do not copy source documents into tickets. |
| Key compromise | Rotate the relevant managed secret, restart API/worker, invalidate sessions as required, and verify old credentials fail. Rotating JWT signing keys invalidates existing sessions. |

Logout persists JWT revocation until expiry. Schedule an owner-reviewed cleanup of expired revocation records; do not delete active entries. Database superusers can alter audit rows: application append-only behavior is not independently tamper-proof storage.

## Backup and recovery

`python -m scripts.restore_drill` accepts only a local `regulaai_verify_*` database in `ENVIRONMENT=test`. It takes a PostgreSQL custom-format dump, collects referenced private source objects, encrypts the bundle, restores to a new `regulaai_restore_*` database and separate object directory, then compares table counts/full-row fingerprints and object bytes. It never restores over the source database. Local recovery keys and archives stay under ignored `output/`; production requires independent managed keys and protected backup storage.

The recorded local drill restored 19 objects in 3.218 seconds. This measures a synthetic snapshot, not production RTO/RPO, point-in-time recovery or cloud backup scheduling. Approve recovery objectives, backup cadence, retention and ownership, then test tenant access after restore through the deployed application.

## Capacity evidence

`python -m scripts.load_local` accepts only a disposable local verification database, creates synthetic fixtures and an isolated queue namespace, and starts/stops only its own API/worker processes. The test sends 100 authenticated reads at concurrency 10 and queues 20 real parser jobs; no model or cloud service is invoked. Reports preserve the slower initial runs and subsequent improvement. Full matrices, large tenants, provider latency, resource saturation and staging capacity remain unmeasured. Do not use this test to size production.
