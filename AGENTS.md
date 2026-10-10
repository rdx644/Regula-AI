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
- `render.hackathon.yaml` is the separate all-free, synthetic-data demo profile. It runs one embedded worker and ephemeral local uploads; it does not satisfy durable S3-backed production gates. Keep `render.yaml` as the S3-backed preview profile.
- **Submission and production gates remain incomplete**: real golden reliability, full semantic change/impact/remediation/investigation demo, F3/D2 claim, development dependency disposition, release-image verification, live staging/TLS/IAM/alerts/retention/backup/rollback and production approval.
- Source-of-truth evidence: `docs/SUBMISSION_READINESS.md`, `docs/evidence/verification.json`, `AGENT_COMPLETION_RUNBOOK.md`; operational/security/evaluation/demo details are linked there. Never promote partial/blocked gates to complete based on fixture output or local tests alone.

## Frontend refinement (2026-10-10)
- Text wordmark replaces the homepage letter icon. Three.js introduction is lazy, finite, paused offscreen and disabled for reduced motion.
- Added authenticated capability discovery, upload limits, unavailable-model states, workspace creation, source download, working findings/remediation view, request cancellation and automatic terminal-job refresh.
- Synthetic demo source pages and initial applicability now match the workflow contract. Existing demo review decisions are preserved; applicability can be explicitly reopened by a reviewer.
- Latest isolated backend verification: 110 passed, 27 warnings. All five automated browser tests, lint, TypeScript and production build pass; frontend runtime audit reports zero vulnerabilities. All five workspace views pass manual axe checks and fit a 390px viewport. See `docs/evidence/frontend-redesign.json` for exact browser/build results and live deployment limits.

## Hackathon submission completion (2026-10-10)
- 114 isolated backend tests pass (28 warnings, 36.69s); five existing browser tests pass (1.6m); lint and TypeScript production build pass.
- Added bounded literal source diff, version/line citations and persisted candidate impact drafts; unchanged source has no draft. Same-source comparisons serialize and identical comparisons reuse the saved report. No semantic inference or baseline mutation.
- Added scenario UI using existing actual worker/snapshot persistence and exports; mapped control outage and bounded illustrative multipliers only. Added guided tenant-scoped investigation with recorded source citations and audit events; no autonomous planning/model call.
- Local CLI browser checks verified all added workflows and reload persistence. Axe has zero violations on all eight workspace views and populated comparison/investigation results; 390px layout fits.
- Live free Render rehearsal verified signup, workspace/demo creation, private parsing/source download, control/mapping/evidence/test review, actual gap worker, post-remediation private evidence/passing test and validated closure surviving reload.
- Submission description, live link, judge sequence and synthetic inputs are in docs/HACKATHON_SUBMISSION.md. No contest submission, paid model call or infrastructure provisioning performed. Original full F3/D2/model/production gates remain incomplete; don't count eight navigation screens as eight accepted hackathon features.
- Latest release/push/live checks are in docs/evidence/hackathon-submission.json; older evidence remains historical.

- Feature release 4d7c2ce is pushed, CI/Blueprint pass, and all new workflows now pass on the live Render demo with reload persistence. Live axe has zero violations on all eight views and populated comparison/investigation; 390px fits. Live logout/signin, second-tenant403 and CSRF403 verified; architecture Pages returns200.
- Follow-up browser regression covers changing workspaces then immediately reloading. Persist the selected organization synchronously, before slower workspace reads. No auth token is stored in localStorage.
