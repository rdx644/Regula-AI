# RegulaAI web application

The Next.js App Router frontend provides account registration and sign-in, an organization-scoped compliance overview, and a traceability matrix linking obligations, controls, evidence, tests, gaps, and remediation.

The interface uses a neo-brutalist theme: warm paper, yellow/lilac/mint/coral accents, heavy Manrope headings, square ink borders and offset shadows. Shared tokens in `src/app/globals.css` style authentication and all eight workspace views. The sign-in trace board uses HTML/SVG and needs no WebGL or animation. Keyboard focus, reduced-motion preferences, narrow-screen navigation and contained table scrolling remain supported. See [design and verification](../docs/FRONTEND_DESIGN.md).

## Run locally

1. Start the repository's local PostgreSQL/pgvector and Redis services with `docker compose up -d postgres redis` from the project root. Configure `backend/.env` from `backend/.env.example` with the local database URL and a unique development `SECRET_KEY`.
2. From `backend/`, run `alembic upgrade head` and start the API with `venv/Scripts/uvicorn app.main:app --reload` on Windows (or `venv/bin/uvicorn app.main:app --reload` on Linux/macOS).
3. Copy this directory's `.env.example` to `.env.local` if the API is not at `http://localhost:8000/api`.
4. From `frontend/`, run `npm run dev` and open `http://localhost:3000`.
5. Create an account or sign in. Choose **Load demo scenario** to create a private, repeatable demo organization and populate the compliance matrix.

The API session uses an HttpOnly cookie and a CSRF token held in page memory. The selected organization ID is stored as a non-secret browser preference and is revalidated by the API. Configure the API origin through `NEXT_PUBLIC_API_URL` when it is not `http://localhost:8000/api`.

## Checks

Run `npm run lint`, `npx next typegen`, `npx tsc --noEmit --incremental false`, and `npm run build` from this directory. Type generation is required on a fresh checkout before checking global Next.js route/layout types.


The control library supports manual control proposals/approval, reviewed mappings, private evidence inspection/review and reviewed tests. The matrix supports applicability/source decisions and tracked gap/remediation jobs. AI execution is disabled pending owner budget approval.

Browser verification: `npx playwright test` starts the test API/worker/web stack using a migrated dedicated PostgreSQL database and isolated Redis namespace. Extraction uses a disclosed synthetic adapter. See `../docs/DEMO_AND_SUBMISSION.md` and `../docs/SUBMISSION_READINESS.md` for current evidence and blocked deployment/quality gates.
