# Reproducible demo and submission draft

**Draft for owner review; not published or submitted.** This checkout does not yet meet the governing plan's final submission or production gate. The F3/D2 targets remain targets.

## Replay the tested synthetic browser workflow

1. Follow `docs/LOCAL_DEVELOPMENT.md` to start local PostgreSQL/pgvector and Redis. Use a dedicated test database, a unique synthetic secret and `ENVIRONMENT=test`. Keep `MODEL_EXECUTION_ENABLED=false`.
2. Install backend `requirements-dev.txt` and frontend dependencies; migrate the test database. Install Chromium with `npx playwright install chromium` if unavailable.
3. From `frontend`, export the test database URL, `REDIS_URL` pointing to an isolated Redis database, and a unique `JOB_QUEUE_PREFIX`. On Windows the Playwright configuration uses `backend/venv/Scripts/python.exe`; set `E2E_PYTHON` for another interpreter.
4. Run `npx playwright test`. The configuration starts its own API (8010), synthetic worker and web server (3010), then stops them. Use these loopback ports only. It creates fresh synthetic users/tenants each run and does not delete an existing tenant. Repeat with another test database/queue namespace for isolation; no destructive reset is required.

The happy test performs registration, organization creation, synthetic upload and real parsing, fixture extraction, exact source inspection, applicability/obligation approval, control creation/approval, mapping proposal, private evidence upload/inspection/review, reviewed manual test, mapping approval and actual deterministic gap-worker completion. Additional tests cover invalid upload, unauthenticated access, CSRF, second-tenant denial, failed job/manual retry, keyboard focus, axe accessibility and 390px layout.

Use `backend/scripts/browser_worker.py` only in `ENVIRONMENT=test`. It supports a single explicit synthetic sentence and intentionally fails other extraction inputs. It is not a general-purpose extraction engine or an OpenAI evaluation.

## Synthetic input

```text
Section 1
The synthetic bank shall review its capital ratio daily.
```

Control: `CTL-SYNTHETIC-DAILY`, daily ratio review with calculation and reviewer sign-off. Evidence is a synthetic UTF-8 log; reviewed effectiveness is .95. Human input supplies control/mapping/test decisions. The application persists and authorizes them; no autonomous model claim is implied.

The **Load demo scenario** endpoint creates a private user-specific prepared tenant and is idempotent. Its Basel-themed values/mappings/evidence are seeded examples, not independently extracted or legally certified source material. Do not use seeded metrics as measured model reliability.

## Demonstration scope

Current screenshot: `docs/evidence/review-workflow.png`. The final automated run passed five tests, including source/control/evidence/mapping review and accessibility. It demonstrates the current synthetic/manual scope.

The exact plan section 43 sequence still requires a reviewed two-version semantic-change/impact scenario, real remediation recommendation and validation closure, a product scenario report, and an investigation question with a grounded answer/audit trace. Those steps must remain labelled incomplete. The persisted bounded scenario service has backend evidence but no complete product simulation UI demo.

## Submission text draft

> RegulaAI connects regulatory sources, reviewed obligations, internal controls, private evidence, test outcomes and compliance findings in a tenant-scoped workspace. It uses structured proposals and human review, deterministic gap/risk calculations, durable background jobs and persisted audit traces. The local synthetic demonstration exercises actual API/database/worker/storage paths. Its extraction adapter is explicitly synthetic; real model reliability evaluation and production deployment are pending owner approvals and operational verification.

Exclude claims of eight/twelve fully validated hackathon features, D2 reliability, autonomous legal interpretation, verified regulatory impact, production readiness and live deployment until their acceptance evidence exists. Use the F01-F14 matrix in `SUBMISSION_READINESS.md` when preparing any later claims.

## Review package

- `SUBMISSION_READINESS.md`: every section 48 item and vertical slice, plus blockers.
- `ARCHITECTURE.md`: actual implemented architecture and omitted planned paths.
- `SECURITY_REVIEW.md`: exercised controls and unresolved development dependencies.
- `ai-evaluation.md`: unpaid evaluation status, label issues, reproducible future runner and assumptions.
- `OPERATIONS.md`: release/rollback, private storage, incident, key rotation, backup/restore and load instructions.
- `evidence/verification.json`: concise local check results and artifact references.

Owner approval remains required for commit/push, paid execution, cloud provisioning/deployment and public submission under the governing runbook. No credentials, recovery keys, browser traces or private backups belong in a submitted package.
