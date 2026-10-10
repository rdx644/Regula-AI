# RegulaAI

### Regulatory compliance and control intelligence for banking teams

[![CI](https://github.com/rdx644/Regula-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/rdx644/Regula-AI/actions/workflows/ci.yml)
[![Render Blueprint](https://github.com/rdx644/Regula-AI/actions/workflows/render-blueprint.yml/badge.svg)](https://github.com/rdx644/Regula-AI/actions/workflows/render-blueprint.yml)

RegulaAI connects regulatory source documents with obligations, internal controls, supporting evidence, compliance tests, gaps and remediation. It gives reviewers a traceable workspace for making and recording compliance decisions. Model-generated outputs are proposals that require review before consequential changes.

[Architecture](#architecture) · [Quick start](#quick-start) · [Deploy on Render](#deploy-on-render) · [Verification](#verification) · [Documentation](#documentation)

> **Project status:** The target is a temporary public hackathon demo using synthetic data and free Render services. Web services sleep; local uploads and Redis data may be lost on restart, and free PostgreSQL expires after 30 days. This configuration is not approved for real bank data. OpenAI execution remains disabled. The separate S3-backed preview configuration is retained.

## Capabilities

| Area | Implemented capability |
| --- | --- |
| Regulatory intake | Private, versioned PDF/text uploads and background parsing |
| Obligations | Source quotes, page references, applicability and approval records |
| Controls | Control review, mapping proposals and explicit mapping decisions |
| Evidence and testing | Private evidence access, validation and reviewed test results |
| Gaps and risk | Deterministic assessment using reviewed records and stated scoring rules |
| Remediation | Reviewed lifecycle with completion guards tied to current evidence and tests |
| Scenarios | Isolated persisted what-if snapshots without changing the underlying landscape |
| Background execution | Tenant-scoped jobs, deduplication, leases, retries and persisted agent traces |

Structured AI agents are implemented, but real golden-set evaluation, semantic change/impact acceptance and some product capabilities remain open. The synthetic extraction adapter used by browser tests does not establish model quality. Submission and production gates are incomplete. See the [feature and readiness matrix](docs/SUBMISSION_READINESS.md) for the exact scope and remaining owner actions.

## Architecture

The logical application uses a Next.js workspace, a FastAPI service and a background worker. The browser sends same-origin `/api` requests through Next.js. PostgreSQL stores domain records and audit history, and Redis coordinates jobs. The free hackathon profile runs the worker inside the API process and stores uploads on ephemeral local disk. S3 is an optional, separate durable deployment profile; the free profile does not use S3.

[![Open the interactive RegulaAI architecture diagram](docs/assets/regulaai-architecture.svg)](https://rdx644.github.io/Regula-AI/architecture/)

**Explore the architecture:** [interactive HTML](.archify/architecture-regulaai-storage-20261010-051216/regulaai.html) · [PNG](docs/assets/regulaai-architecture.png) · [SVG](docs/assets/regulaai-architecture.svg) · [diagram verification](docs/evidence/architecture-diagram.json).

**Interactive diagram:** The [standalone HTML](.archify/architecture-regulaai-storage-20261010-051216/regulaai.html) works locally and includes source links, light/dark themes and image exports. The [SVG preview](docs/assets/regulaai-architecture.svg) is shown in this README; GitHub does not run embedded interactive HTML. A [GitHub Pages workflow](.github/workflows/architecture-pages.yml) publishes the interactive page at [rdx644.github.io/Regula-AI/architecture](https://rdx644.github.io/Regula-AI/architecture/) after Pages is enabled for the repository. **One-time setup:** in GitHub, open **Settings → Pages** and choose **GitHub Actions** as the build and deployment source. Until that is done, the Pages workflow cannot publish and the live URL may be unavailable. Local validation, delivery, artifact, and browser checks for the Archify artifact passed; this does not verify GitHub Pages or a deployed application. See [architecture notes and request sequence](ARCHITECTURE.md) for implementation boundaries.

### Technology stack

| Layer | Technology |
| --- | --- |
| Web workspace | Next.js App Router, React, TypeScript, Tailwind CSS, Three.js |
| API | Python 3.12, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL 16, pgvector, Alembic migrations |
| Jobs and workflows | Redis, asynchronous workers, LangGraph workflows |
| File storage | Ephemeral local adapter for the hackathon demo; S3-compatible storage for durable deployments |
| Model integration | OpenAI SDK, structured outputs and execution quotas; disabled by default |
| Verification | pytest, Playwright, axe accessibility checks, GitHub Actions |
| Packaging | Docker, Docker Compose, Node.js 22, Render Blueprint |

## Compliance workflow

1. Upload a source document and inspect the parsed content.
2. Review proposed obligations against source quotes and record applicability.
3. Review controls and approve or reject obligation-to-control mappings.
4. Attach private evidence and review compliance test results.
5. Assess deterministic gaps and risk against the reviewed landscape.
6. Record remediation decisions and validate completion against current evidence.

The [synthetic demo guide](docs/DEMO_AND_SUBMISSION.md) makes the tested path reproducible and identifies fixture-backed steps. Human review remains part of the workflow.

## Workspace experience

- **Overview**: compliance posture, traceability and an attention queue based on recorded workspace data.
- **Regulatory library**: private source upload, parsing, source download and background-job progress. The upload limit comes from the API (10 MB on the free Render profile).
- **Control library**: propose and approve controls, record manual mappings, upload and inspect evidence, and save reviewed tests.
- **Compliance matrix**: search clauses and controls, inspect source citations, record applicability, approve mappings and assess deterministic gaps.
- **Gap & remediation**: filter findings, propose a manual action plan, assign an owner and advance reviewed plans. Completion requires current evidence and a passing post-remediation test.

After signing in, create a named workspace or select **Load demo scenario** to use the synthetic Basel III dataset. New demo obligations include applicability and synthetic source pages. For older demo records marked `approved / uncertain`, open **Review source**, choose **Reopen obligation review**, and explicitly approve the applicability before assessing gaps. Reloading the demo repairs missing synthetic source pages without changing previous decisions. Organization changes clear the previous view and cancel obsolete requests. Completed jobs refresh the relevant results automatically.

The entry page uses locally served Manrope/Newsreader typography and a short, lazily loaded Three.js compliance-chain animation. Reduced-motion and WebGL fallback paths render a static diagram; hidden or finished animations stop rendering. The homepage uses a text wordmark without the former letter icon.

**Free demo behavior:** model execution remains disabled. Source parsing, manual reviews and deterministic gap assessment work without paid AI. Assisted actions display as unavailable, and uploads parse without automatically starting extraction. Live extraction requires separate execution and spending approval. Browser verification uses an explicitly disclosed extraction fixture restricted to the test environment.

## Quick start

### Prerequisites

- Python 3.12 and Node.js 22
- Docker with Docker Compose
- Git; the commands below use PowerShell

### 1. Clone and start infrastructure

```powershell
git clone https://github.com/rdx644/Regula-AI.git
cd Regula-AI
docker compose up -d postgres redis
```

### 2. Configure and start the API

```powershell
cd backend
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Set a unique `SECRET_KEY` in `backend/.env` and review the database, Redis and storage settings. Keep `MODEL_EXECUTION_ENABLED=false`. Development credentials must not be reused for a deployed environment.

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### 3. Start the worker in another terminal

From the repository root:

```powershell
cd backend
.\venv\Scripts\python.exe -m app.workers.main
```

### 4. Start the workspace in another terminal

From the repository root:

```powershell
cd frontend
npm ci
$env:NEXT_PUBLIC_API_URL = "/api"
$env:API_PROXY_ORIGIN = "http://localhost:8000"
npm run dev
```

Open **http://localhost:3000** and create a synthetic account. The local API runs at **http://localhost:8000**. See [local development](docs/LOCAL_DEVELOPMENT.md) for environment details and [demo setup](docs/DEMO_AND_SUBMISSION.md) for reproducible sample data.

## Deploy on Render

The [hackathon blueprint](render.hackathon.yaml) defines free web, API, PostgreSQL and Redis services in Singapore. The API starts a single embedded worker and uses temporary local upload storage; no S3 account is required. The separate [render.yaml](render.yaml) retains the S3-backed preview topology with a paid worker.

1. Open [Create a Render Blueprint](https://dashboard.render.com/blueprint/new?repo=https://github.com/rdx644/Regula-AI), connect the repository and branch `main`, then set the blueprint path to `render.hackathon.yaml`.
2. Confirm every listed service uses the **Free** plan. This blueprint has no separate paid worker and does not require S3.
3. Select **Deploy Blueprint**. Render generates application secrets and links the API, frontend, database and Redis settings automatically.
4. Open the assigned frontend URL. Verify HTTP 200 from `/api/health/live` and `/api/health` through that hostname. Readiness checks PostgreSQL, Redis and the embedded worker. The web service has been reachable, but API readiness was still failing during the latest local frontend review; complete these checks before sharing the demo.
5. Create a synthetic account and use synthetic documents. Re-upload if a service restart clears local uploads.

Free web services sleep, free PostgreSQL expires after 30 days without managed backups, and free Key Value data can be lost on restart. Web/API filesystems are ephemeral. This profile is for a short synthetic demo. See [Render free service limits](https://render.com/docs/free) and the [complete Render guide](docs/RENDER_DEPLOYMENT.md). The separate S3-backed preview uses paid compute and requires an owner-provided bucket.

## Security and review controls

- HttpOnly session cookies, CSRF protection and persisted logout revocation
- Tenant authorization for domain records, linked resources, jobs and downloads
- Worker checks of the initiating actor's current permissions
- Private source/evidence storage and upload validation
- Source-quote checks, structured proposal validation and explicit human review
- Redacted logs, audit trails, protected metrics and configuration readiness checks

Local backend and frontend runtime dependency audits reported no known vulnerabilities. Five high findings in frontend development tooling remain disclosed in the [security review](docs/SECURITY_REVIEW.md). Cloud IAM and deployment controls have not been verified. Keep credentials, bank documents, source uploads, recovery keys, browser traces and local `output/` artifacts out of Git.

## Verification

Use isolated test PostgreSQL/Redis services and the environment described in [local development](docs/LOCAL_DEVELOPMENT.md). Backend checks from `backend/`:

```powershell
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m alembic check
```

Frontend checks from `frontend/`:

```powershell
npm run lint
npx next typegen
npx tsc --noEmit
npm run build
npx playwright test
```

Before browser verification, install Chromium with `npx playwright install chromium` and configure the dedicated test database, Redis namespace and synthetic settings in the [demo guide](docs/DEMO_AND_SUBMISSION.md). Playwright starts its own test API, worker and frontend.

| Evidence | Observed result |
| --- | --- |
| Local backend suite | 110 passing tests, including PostgreSQL/Redis authorization, worker and frontend capability checks (recorded 2026-10-10) |
| Automated browser suite | Five passing tests; axe, keyboard and narrow-screen checks on covered pages. Manual axe checks also pass on all five signed-in views (recorded 2026-10-10) |
| Database migrations | Head `f5a6b7c8d9e0`; fresh migrations and drift checks pass |
| Frontend | Lint, type checking and production build pass (recorded 2026-10-10) |
| GitHub CI | Main CI and Render Blueprint validation passed at source revision `9e0ca67`; see the workflow badges above for current status |
| GitHub Pages | The workflow requires Pages to be enabled with **GitHub Actions** under **Settings > Pages**; until then, the interactive URL is unavailable |
| Render Blueprint CI | [Passing run at `9e0ca67`](https://github.com/rdx644/Regula-AI/actions/runs/37998241179) |
| Architecture diagram | Local validation, delivery, artifact and browser gates pass; light/dark visual review completed. These checks do not verify a live deployment. |
| Real model evaluation | Not run: zero predictions; ten golden inputs await budget and label review |

[Frontend redesign verification](docs/evidence/frontend-redesign.json) records the latest workflow and visual checks. [Local verification evidence](docs/evidence/verification.json) records the earlier engineering audit and its limitations. These results establish the covered behavior, not production capacity, comprehensive penetration testing or regulatory model reliability. Current badges show the latest workflow state; the run links above preserve the observed source-revision evidence.

## Repository layout

```text
backend/
  app/             API, domain services, agents and workers
  alembic/         Database migrations
  evaluation/      Golden-set inputs and scoring support
  scripts/         Operator and verification tools
  tests/           Backend and integration checks
frontend/          Next.js workspace and browser tests
docs/              Setup, security, operations and evidence
.archify/          Architecture specification and interactive HTML
.github/workflows/ Continuous integration
render.yaml        Render preview blueprint
compose.yaml       Local infrastructure
```

## Documentation

| Document | Purpose |
| --- | --- |
| [Architecture](ARCHITECTURE.md) | Current implementation, persistence boundaries and request flow |
| [Local development](docs/LOCAL_DEVELOPMENT.md) | Configuration, service startup and verification |
| [Synthetic demo](docs/DEMO_AND_SUBMISSION.md) | Reproducible sample workflow and submission boundaries |
| [Render deployment](docs/RENDER_DEPLOYMENT.md) | Plans, managed settings, routing and deployed checks |
| [Operations](docs/OPERATIONS.md) | Recovery, load testing, observability and rollout procedures |
| [Security review](docs/SECURITY_REVIEW.md) | Reviewed controls and unresolved findings |
| [AI evaluation](docs/ai-evaluation.md) | Evaluation contract, assumptions and current blockers |
| [Submission readiness](docs/SUBMISSION_READINESS.md) | Feature-by-feature acceptance and remaining gates |
| [Completion runbook](AGENT_COMPLETION_RUNBOOK.md) | Governing acceptance criteria and execution record |

## Contributing

Keep changes scoped and traceable. Preserve tenant boundaries, source citations and human-review checks; use synthetic fixtures for examples and verification. Document relevant behavior changes and update the readiness evidence when a gate is actually completed. Never commit secrets or private customer data.
