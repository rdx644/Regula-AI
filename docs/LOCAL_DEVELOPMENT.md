# Local development and verification

RegulaAI uses PostgreSQL with pgvector and Redis for its local data and job queue. The included Compose file starts only these dependencies; it does not deploy the API, worker, or frontend.

## Start dependencies

```powershell
docker compose up -d postgres redis
```

The Compose ports bind to loopback. Its database password is intentionally for local development only and must never be reused outside a developer machine.

## Configure and run the backend

From `backend`, create a private `.env` from `.env.example` and replace `SECRET_KEY` with a sufficiently long unique local value; do not commit `.env` or paste its contents into logs or issue reports. The example database URL matches the development-only Compose service.

```powershell
venv\Scripts\alembic.exe upgrade head
venv\Scripts\uvicorn.exe app.main:app --reload
```

In a second backend terminal, start the queue worker:

```powershell
venv\Scripts\python.exe -m app.workers.main
```

## Run the frontend

From `frontend`:

```powershell
npm ci
npm run dev
```

The development UI expects the API at `http://localhost:8000/api` unless `NEXT_PUBLIC_API_URL` is set. Browser sessions use an HttpOnly cookie and a CSRF header; the token is not persisted in Web Storage.

## Verification

```powershell
# backend (from backend)
venv\Scripts\python.exe -m pip check
venv\Scripts\python.exe -m pytest -q

# frontend (from frontend)
npm run lint
npx next typegen
npx tsc --noEmit --incremental false
npm run build
```

GitHub Actions runs PostgreSQL/Redis backend checks, migrations/drift, security tests, worker imports, audits, frontend lint/type/build, and synthetic browser E2E. [Main CI](https://github.com/rdx644/Regula-AI/actions/runs/37998241134) and [Render Blueprint CI](https://github.com/rdx644/Regula-AI/actions/runs/37998241179) passed at source revision `9e0ca67`. Fresh checkouts generate Next.js route types before running TypeScript checks.

## Production gates not satisfied by local checks

Before handling real bank documents, configure and verify a private S3-compatible bucket, deployment-specific secret material, TLS and trusted hosts, Redis-backed rate limiting, monitoring/alerting, and an upload/body-size limit at the public edge. Deploy the browser and API under the same site so the `SameSite=Lax` session cookie works as intended. Complete a staging deployment, browser end-to-end tests, backup/restore drill, load test, and a scored run of the golden evaluation set. The current synthetic/demo and unit-test evidence does not demonstrate D2 model reliability or production readiness.


## Automated browser and local operational checks

`frontend/playwright.config.ts` starts its own API, synthetic extraction worker and frontend for `npx playwright test`. Use `ENVIRONMENT=test`, a dedicated migrated PostgreSQL database, isolated Redis database/queue namespace and a unique test `SECRET_KEY`. Only extraction model responses are fixtures; private intake, parsing, workers, persisted manual reviews and authorization are real. No paid model call is required. See `docs/DEMO_AND_SUBMISSION.md`.

Model execution defaults to `MODEL_EXECUTION_ENABLED=false` and remains off until budget/data use is approved. `OPENAI_API_KEY` alone cannot enable it. The golden runner requires a separate explicit execution flag; no predictions have been run.

From backend, `python -m scripts.fresh_migration`, `python -m scripts.restore_drill` and `python -m scripts.load_local` require a local database named `regulaai_verify_*` with `ENVIRONMENT=test`. They create isolated databases/fixtures and never restore over the source. Keep `output/` private: it contains recovery keys, encrypted archives and browser traces. Do not upload it to GitHub or a submission.
