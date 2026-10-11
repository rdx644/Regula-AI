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

The proxy preserves trailing slashes: `/api/users/` and `/api/organizations/` must reach FastAPI with their slash intact. Next.js automatic slash redirects are disabled, and separate rewrite patterns preserve both forms. A frontend rebuild is required for this routing change.

### Signup/sign-in returns 500 or 502

The free API instance can sleep independently of the frontend. On 2026-10-11,
the homepage returned 200 while proxied health checks initially returned 502
and direct API checks timed out. By 08:43:55 UTC both direct and proxied
liveness/readiness returned 200; readiness reported PostgreSQL and Redis
connected and the worker healthy. This recovery is consistent with a cold start,
but Render Events are needed to distinguish sleep from a restart.

The browser API helper retries GET requests on network failures and 502/503/504
responses, with five attempts and a two-minute overall deadline. Retry delays
are 5, 10, 20 and 30 seconds, and navigation/unmount cancellation stops the wait.
Writes are not automatically replayed. Authentication failures and rate limits
return immediately. Run `cd frontend; npm run test:api` to check this behavior.

The PyMuPDF `fitz` deprecation warning does not establish a startup failure:
the supplied deployment logs show application startup completed after it.
The parser now uses `import pymupdf` and closes PDF documents after parsing.
No dependency upgrade is required for the pinned PyMuPDF version.

1. Check the web service's `/api/health/live` and `/api/health`. A working homepage alone does not establish that authentication is available.
2. Open the API service's public URL from its Render Dashboard and check the same paths directly. Free services can need time to wake up. If direct liveness remains unavailable, inspect API **Logs** and **Events** for startup, migration, restart or memory errors.
3. If direct API health works but the web proxy fails, confirm the web service's `API_PROXY_ORIGIN` exactly matches the API's HTTPS origin (no `/api` suffix). Save the setting and rebuild the web service, because rewrites are compiled at build time.
4. If liveness works but readiness reports a disconnected database or Redis, verify the API references the active resources' internal connection strings. Inspect migration logs; do not reset or drop the database to troubleshoot.
5. If both health checks pass but signup still returns 500, capture the API error type and request ID at the failure time. Do not share credentials, cookies, SQL parameters or connection strings.

Deployment incident check on 2026-10-10: `https://regulaai-hackathon-web.onrender.com/` returned HTTP 200, while proxied health endpoints returned HTTP 502. The API hostname declared in the blueprint timed out on repeated checks. Signup's slash URL also returned a Next.js 308 redirect, prompting the slash-preservation correction. Owner-provided API logs subsequently confirmed exit status 127: the shell treated the entire quoted migration/server command as an executable name. This prevented migrations and Uvicorn from starting and left no listening port. Both API blueprints now run `python /app/start_render.py`; the Dockerfile copies this script into the image. Live recovery remains to be verified after redeployment.

For an existing service that retains the old command, open **regulaai-hackathon-api → Settings → Docker Command** and replace it with `python /app/start_render.py` (no surrounding quotes). Save and deploy the latest commit. Blueprint-managed services can instead sync/apply the updated `render.hackathon.yaml`. The new script requires the rebuilt image; restarting an older image will not include it. Do not change the frontend Docker command.

On the single-instance free API, `start_render.py` runs `alembic upgrade head` with explicit Python arguments before replacing itself with Uvicorn. A migration failure prevents startup. Uvicorn binds to `0.0.0.0` on Render's `PORT` (default `10000`) and receives shutdown signals directly. FastAPI starts/stops the one-slot embedded worker with its app lifecycle. API liveness is the Render deploy probe; the full readiness endpoint checks PostgreSQL, Redis and a fresh worker heartbeat. Automatic deploys use `checksPass`; review the source revision and workflow status before sharing the demo.

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


## Frontend workspace update (2026-10-10)

Redeploy both the API and web services after pulling the frontend redesign. The web now reads the authenticated `/api/auth/capabilities` endpoint to display model availability and the upload limit. An older API will return 404 for this endpoint.

For the free API service, set the Docker Command to `python /app/start_render.py` without surrounding quotes and deploy the latest source. The script runs migrations, then binds Uvicorn to Render's assigned port. Set the web service's `API_PROXY_ORIGIN` to the API service's public origin, without `/api` at the end. Keep `NEXT_PUBLIC_API_URL=/api` and `MODEL_EXECUTION_ENABLED=false`.

Once the API is healthy, open the web app and load the synthetic demo. For existing obligations with uncertain applicability, review the source, reopen the obligation decision and approve applicability explicitly before gap assessment. Reloading the demo restores missing synthetic page context; prior review decisions are preserved.
