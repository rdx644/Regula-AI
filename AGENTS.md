# RegulaAI - Project Memory and Requirements Lock

## Project Purpose
Build a production-grade, agentic banking regulatory compliance platform that maintains a continuously traceable relationship: Regulations -> Obligations -> Applicability -> Internal Policies/Controls -> Evidence -> Testing -> Gaps -> Remediation -> Ongoing Monitoring.

## Hackathon Requirements
Problem 1: Agentic Regulatory Compliance & Control Intelligence Platform. 
Features required include regulatory ingestion, obligation extraction, bank control mapping, gap identification, risk prioritization, remediation recommendation, and autonomous regulatory impact analysis.

## Target Position
F3 (at least 8 hackathon features, targeting 12/14) + D2 (highly reliable structured/textual processing with controlled evaluation).

## Approved Stack
- **Frontend**: Next.js (App Router, Tailwind CSS, TypeScript).
- **Backend**: FastAPI (Python).
- **Database**: PostgreSQL + pgvector for semantic search.
- **Orchestration**: LangGraph / LangChain for Agent workflows.
- **Storage**: Private object storage.

## Architecture
Modular monolith. Separate domain logic from UI. DB is the system of record. AI output requires validation. Deterministic rules where possible. (See `ARCHITECTURE.md`).

## Security Rules
1. Never commit secrets.
2. Every endpoint validates input, authenticates, and authorizes.
3. Every tenant query must be organization-scoped.
4. Prevent prompt-injection by sandboxing untrusted content.
5. No silent mutations by agents.

## AI Rules
- AI outputs must use structured schemas.
- Critical outputs require provenance/citations.
- Low-confidence outputs require human-in-the-loop (HITL) approval.
- High-risk or externally consequential actions require human approval.

## Testing Rules
- Unit tests, integration tests, E2E tests, and security checks must be implemented.
- Do not modify tests to hide failures.
- Benchmark and golden dataset required for AI reliability (D2).

## Definition of Done
Code is not complete unless:
- Requirements are met.
- Input validation, authentication, authorization, error handling, logging are implemented.
- Tests added and passing (lint, typecheck, unit, security).
- Documentation updated and no secrets exposed.

## Commands
- Backend: `cd backend; venv/Scripts/uvicorn app.main:app --reload` (Windows)
- Backend migrations: `cd backend; venv/Scripts/alembic upgrade head` (Windows)
- Backend tests: `cd backend; venv/Scripts/python -m pytest -q`
- Frontend: `cd frontend; npm run dev`
- Frontend checks: `cd frontend; npm run lint`, `npx next typegen`, then `npx tsc --noEmit --incremental false`

## Repository Structure
- `/frontend`: Next.js web application.
- `/backend`: FastAPI service.
- `/docs`: System design and ADRs.
- `ARCHITECTURE.md`: High-level system workflow.

## Current Implementation Status
- Local completion audit (2026-10-10): 104 PostgreSQL/Redis backend tests passed in 54.78 seconds; 27 deprecation warnings. Fourteen worker handlers import; dependency consistency and undefined-name checks pass.
- Fresh disposable database migrated to `f5a6b7c8d9e0`, pgvector 0.8.7; `alembic check` reports no drift. Three additive migrations were added after `b2c3d4e5f6a7`.
- Frontend lint, TypeScript check and production build pass. Five automated browser tests pass, including axe, keyboard focus, narrow-screen layout, actual private upload/parser/worker/persistence, manual control/mapping/evidence/test review, CSRF/tenant denial and failure/retry. Only extraction is a disclosed synthetic model adapter.
- Implemented durable session revocation, stronger reviewer permissions, tenant-safe linked resources, atomic queue/lease/backoff/timeout/replay, input-revision reassessment, exact citations, private evidence/source access, deterministic gap/risk and isolated scenario persistence, human-review proposals and remediation validation guards.
- Added redacted logs, production readiness, protected Prometheus metrics, quota reservations, release templates, CI security/browser checks and operator procedures.
- Real isolated encrypted restore recovered PostgreSQL and 19 source objects in 3.218 seconds. Local 100-request/20-parser-job load had zero errors; throughput improved to 40.77 reads/sec, with p95 2281 ms. These do not establish cloud recovery or production capacity.
- Backend audit and frontend runtime audit have zero known vulnerabilities. Five high frontend development-tool findings remain open and disclosed. Docker Hub HTTP 500/504 errors blocked both release-image builds.
- User supplied `https://github.com/rdx644/Regula-AI.git`; a project-local Git root/origin exists. The prior local audit ended without commit/push. The owner subsequently authorized GitHub publication and Render blueprint preparation, explicitly selecting **prepare/push only; approve plans and secrets in Render**. See `docs/RENDER_DEPLOYMENT.md`; keep cloud provisioning outside this authorization.
- OpenAI provider approved, but latest owner instruction is **keep evaluation unpaid until a budget is provided**. `MODEL_EXECUTION_ENABLED=false` by default. Ten golden items have zero real predictions; label/source issues need review. No OpenAI call was made during this work.
- Automatic approval review rejected expansion of private controls/evidence/gaps into OpenAI prompts; that patch was not applied. Private-data egress approval is separate from provider/budget approval.
- GitHub CI and Render Blueprint CI passed at published source revision `9e0ca67`. README architecture assets are generated with Archify and cite that committed source revision; `docs/evidence/architecture-diagram.json` records their checks.
- **Submission and production gates remain incomplete**: real golden reliability, full semantic change/impact/remediation/investigation demo, F3/D2 claim, development dependency disposition, release-image verification, live staging/TLS/IAM/alerts/retention/backup/rollback and production approval.
- Source-of-truth evidence: `docs/SUBMISSION_READINESS.md`, `docs/evidence/verification.json`, `AGENT_COMPLETION_RUNBOOK.md`; operational/security/evaluation/demo details are linked there. Never promote partial/blocked gates to complete based on fixture output or local tests alone.
