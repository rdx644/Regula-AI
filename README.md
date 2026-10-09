# RegulaAI

Regulatory compliance workspace built with Next.js, FastAPI, PostgreSQL/pgvector, Redis workers and private storage.

## Current gate

**Local verification: 104 backend tests and five browser tests pass; lint, typecheck, build and fresh migrations pass. Submission/production readiness remains incomplete.** Model evaluation is unpaid pending an owner budget. Staging, remote CI, image verification and remaining feature/security acceptance need completion.

Start with [local setup](docs/LOCAL_DEVELOPMENT.md), [reproducible synthetic demo](docs/DEMO_AND_SUBMISSION.md), [readiness matrix](docs/SUBMISSION_READINESS.md) and [verification evidence](docs/evidence/verification.json).

## Documentation

- [Actual architecture](ARCHITECTURE.md)
- [Governing completion runbook](AGENT_COMPLETION_RUNBOOK.md)
- [Operations and deployment handoff](docs/OPERATIONS.md)
- [Render deployment setup](docs/RENDER_DEPLOYMENT.md) and [Blueprint](render.yaml)
- [Security review and unresolved findings](docs/SECURITY_REVIEW.md)
- [Evaluation contract, blockers and assumptions](docs/ai-evaluation.md)

The browser uses an HttpOnly session cookie and CSRF header. Downloads require tenant authorization. AI outputs are proposals; high-impact decisions require review. The test extraction provider is explicitly synthetic and is not model-quality evidence. `MODEL_EXECUTION_ENABLED=false` remains the default.

Never commit private environment files, source uploads, model credentials, recovery keys, browser traces or the local `output/` directory. No public deployment or submission has been made.
