# ADR 0002: Completion security and review boundaries

## Status

Implemented locally, 2026-10-10; deployment and measured AI acceptance pending.

## Decisions

- Keep the modular monolith and separate worker. Use PostgreSQL as the persistent record and Redis for bounded job delivery/leases/retries; do not replace integration verification with SQLite.
- Persist JWT revocation on logout and recheck a queued job actor's current permission before execution. Hold PostgreSQL execution locks and replay completed results; use tenant/input-revision deduplication and lease ownership checks.
- Require explicit human review for obligation/applicability, control, mapping, evidence, test and remediation decisions. Persist evidence/test model proposals without automatically validating them. Require private current reviewed evidence for passing tests and a new post-plan reviewed test for remediation completion.
- Preserve exact extraction source spans/pages and reject foreign/unknown model-selected record IDs. Keep error/log metadata redacted.
- Use deterministic gap/risk and scenario calculations with disclosed assumptions; they require domain calibration and do not replace legal interpretation.
- Upgrade vulnerable dependencies and use PyJWT for issuer/audience/expiry/jti validation. Remove unused runtime orchestration/community/Jose dependencies. Open frontend development-tool advisories remain disclosed.
- Disable paid model execution by default, even if credentials exist. Owner provider approval is separate from spending/data-transfer approval. Automatic review rejected expanding private source/control/evidence/gap prompts, and that expansion was not applied.
- Prepare provider-neutral release artifacts until the owner supplies an authorized staging target. Local S3, restore and load evidence cannot satisfy cloud IAM, operational recovery, monitoring or deployment gates.

## Consequences

The local synthetic/manual workflow is reproducible and covered by tests. Model reliability, full semantic change/impact/investigation demo, F3/D2 claims, remote CI, cloud deployment and operational acceptance remain separate incomplete gates. See `docs/SUBMISSION_READINESS.md` for every requirement and its evidence.
