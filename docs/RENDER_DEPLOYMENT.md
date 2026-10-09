# Deploy the temporary RegulaAI hackathon demo on Render

## Scope and authorization

The owner authorized preparing and pushing deployment files, while approving resource plans and configuration in Render. The target is a temporary hackathon demo on free services. This work does not provision resources or claim a live deployment. `MODEL_EXECUTION_ENABLED=false`; no OpenAI key or S3 account is needed for this profile.

## Blueprint topology

| Resource | Plan | Purpose |
| --- | --- | --- |
| `regulaai-hackathon-web` | Free web | Next.js Docker application; same-origin `/api` proxy |
| `regulaai-hackathon-api` | Free web | FastAPI plus one embedded queue worker |
| `regulaai-hackathon-postgres` | Free | PostgreSQL 16; migrations enable pgvector |
| `regulaai-hackathon-redis` | Free | Internal-only Key Value with `noeviction` |
| Upload storage | Ephemeral local disk | Synthetic demo files only; may disappear on restart or redeploy |

All Render resources use Singapore. The separate root `render.yaml` remains the S3-backed preview with paid standalone worker. Free web services sleep, free Postgres expires after 30 days without managed backups, free Key Value data can be lost on restart, and local uploads are ephemeral. These limits make this a **temporary synthetic demo**, not durable or banking production hosting. See [Render free limits](https://render.com/docs/free).

## Dashboard steps

1. Open [Create a Render Blueprint](https://dashboard.render.com/blueprint/new?repo=https://github.com/rdx644/Regula-AI), select the workspace, authorize GitHub if prompted, and set branch `main` with blueprint path `render.hackathon.yaml`.
2. Review the resource list and confirm all four services use the **Free** plan. If the workspace has reached a free database or Key Value limit, Render may require removal of another unused resource or a different workspace.
3. Select **Deploy Blueprint**. The blueprint generates signing and metrics secrets, references the API and frontend hostnames automatically, and creates internal PostgreSQL/Redis references. No S3, AWS credentials, manual CORS origin or model key is requested.
4. Wait for the API and frontend builds. The API runs migrations, then starts FastAPI and a single embedded worker. A build or migration failure must be fixed before continuing.
5. Use the frontend URL Render assigns. The API proxy URL is injected into the frontend build; hostname changes require a frontend rebuild.

The demo environment sets Secure session cookies, CSRF protection, explicit HTTPS CORS/host restrictions, Redis-backed rate limiting, and one worker slot. Model execution stays off. The `demo` application mode accepts local storage only for this explicitly temporary profile; `staging` and `production` continue to require private S3.

### Routing and deploy order

The browser uses relative `/api` calls. Next.js rewrites them to the API service, preserving one browser origin for the HttpOnly session and CSRF cookies. The public API origin is compiled into the frontend; changing it requires rebuilding the frontend. No backend credential is passed as a frontend build argument. See [Render Docker environment translation](https://render.com/docs/docker).

On the single-instance free API, the start command runs `alembic upgrade head` before Uvicorn. A migration failure prevents startup. FastAPI starts/stops the one-slot embedded worker with its app lifecycle. API liveness is the Render deploy probe; the full readiness endpoint checks PostgreSQL, Redis and a fresh worker heartbeat. Automatic deploys use `checksPass`; review the source revision and workflow status before sharing the demo.

The API and worker share a free web process, so a cold start delays both and memory/CPU are constrained. Do not scale API replicas with the embedded worker enabled. Local uploaded files can disappear independently from PostgreSQL records; Redis may reset queued work, rate-limit counters and sessions. Only use disposable synthetic data. The existing S3-backed `render.yaml` is the separate paid preview profile; neither profile alone proves banking production readiness.

## Verify after Apply

1. Confirm both web services are live and identify the deployed Git revision; review logs for migration/startup failures without exporting secrets or documents.
2. Through the frontend HTTPS hostname, request `/api/health/live` and `/api/health`. Require HTTP 200 for both. Readiness checks PostgreSQL, Redis and the embedded worker heartbeat; local storage is intentionally ephemeral.
3. Sign up/sign in with a synthetic user. Confirm cookies are Secure, HttpOnly for the session, and confined to the frontend origin. Verify invalid/missing CSRF tokens fail and logout revokes the session.
4. Use synthetic documents to upload, parse, inspect/download, approve an obligation, create/review a control, map it, review evidence/tests and assess deterministic gaps. Model execution stays off; use only the disclosed synthetic fixture for extraction demonstrations.
5. Verify second-tenant denial, failed-job retry, CSRF rejection, logout and invalid/large upload handling.
6. Record deployment URL, IDs, revision, CI run and checks in the completion runbook. Explain that free-service data is disposable and that the demo is not for banking production.

## Configuration validation

The hackathon blueprint is validated against Render's published schema. Workspace-aware CLI validation is not available without a selected Render workspace. Schema validation does not prove resource availability, image builds or live service behavior. The owner reviews all resources in the Dashboard before deployment.
