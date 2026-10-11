# Neo-brutalist frontend

The 2026-10-11 frontend revision replaces the green editorial theme with a graphic neo-brutalist design across sign-in, registration and all eight workspace views.

## Visual system

- Ink: `#191919`; paper: `#f6f3e9`; cards: `#fffef8`.
- Accents: yellow `#ffe45c`, lilac `#c6b8fa`, mint `#c4e9c4`, coral `#ff9a82`.
- Manrope Variable for body and heavy display headings; monospace labels for navigation indices, source metadata and statuses.
- Square two-pixel borders, solid offset shadows and buttons that press into their shadows.
- Status labels retain readable text and semantic colors. Color alone does not convey a decision or finding.

`frontend/src/app/globals.css` holds the shared tokens, component styles and responsive breakpoints. Authentication uses a poster layout, outlined form and tilted source/action cards. `TraceScene.tsx` now renders HTML/SVG rather than importing Three.js; it is visible immediately and does not depend on WebGL. The Newsreader font is no longer loaded.

This is a presentation change. Existing authentication, workspace selection, source review, uploads, control/evidence/test decisions, comparison, scenarios and investigation handlers are preserved. The separately prepared cold-start GET retries and PyMuPDF correction remain in the local working tree.

## Local verification

- Frontend lint and production build, including TypeScript compilation, passed.
- The eight workspace views were inspected in a real Chromium browser at 1440px and 390px with isolated synthetic API routes. All sixteen view/viewport combinations had zero axe violations, zero visible API errors and no page-level horizontal overflow.
- Sign-in passed axe and overflow checks at 1440px, 390px and 320px. Registration passed at 320px. Keyboard focus remained visible and reduced-motion disabled transitions.
- Source review, a saved text comparison and an investigation result were opened and captured using the same synthetic routes.
- No browser JavaScript exceptions occurred during this review.
- These fixture checks validate presentation and browser interactions. They do not verify live authentication, real backend writes, tenant isolation or persistence. The full PostgreSQL/Redis browser suite was not rerun for this styling change.

The machine-readable receipt is [frontend-neobrutalism.json](evidence/frontend-neobrutalism.json). Local screenshots and the CLI review scripts are in ignored `output/playwright/`. `neo-login-1440.png`, `neo-login-390.png`, `neo-1-1440.png` and `neo-1-390.png` provide entry/overview comparisons; numbered images 1–8 cover all navigation views.

This verification was performed on the local working tree before publication. It does not establish the deployed revision. Historical live-release evidence applies to the previous design until the new revision is deployed and verified.
