# Security verification summary

Date: 2026-10-10. Scope: local synthetic PostgreSQL/Redis integration, application code, browser workflows and local S3 emulator. No bank data or production account was used.

## Implemented and exercised

- Cookie/CSRF authentication, issuer/audience/expiry claims, persisted logout revocation and role checks.
- PostgreSQL tenant denials across resource lists/details/creates/updates, private file downloads, matrix/metrics and job reads; worker queries carry tenant scope and current actor permissions are rechecked.
- Atomic queue deduplication, bounded retry/backoff, lease recovery, terminal failures/timeouts, replay of completed execution and rejection of stale worker results.
- Reviewer permissions for obligations, controls, mappings, evidence and tests. AI evidence/testing outputs are proposals. Control owners cannot self-approve controls. Remediation state transitions and evidence-backed completion are enforced.
- Private uploads use allowlisted PDF/UTF-8 TXT/Markdown, bounded reads, binary rejection, path containment and tenant key prefixes. S3 emulator checks exercise encryption/versioning/public-access configuration.
- Injection pattern detection/sanitization, exact extraction citation validation, invalid model-schema error redaction, quota refusal before a mocked model call and a disabled-by-default provider switch.
- Request ID validation, structured identifier-only request logs, SDK/SQL debug suppression and validation errors that omit input values. Operator metrics require a separate managed credential.

See `backend/tests/test_final_release_gates.py`, `test_completion_regressions.py`, `test_completion_queue_security.py`, existing auth/middleware/worker/storage tests, and `frontend/e2e/workflow.spec.ts`. These tests demonstrate the specified cases; they are not a penetration test or proof that every adversarial prompt is blocked.

## Dependency findings

Backend vulnerable packages were upgraded; unused LangChain/community/Jose adapters were removed from declared runtime requirements. JWT verification now uses PyJWT. The local full-environment `pip-audit` found no known vulnerabilities after updates. Frontend runtime `npm audit --omit=dev` found zero vulnerabilities.

The full frontend development dependency tree has five high findings associated with `braces` through lint/build tooling. The [maintainer advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) lists no patched version for the reported path. This finding remains **open**, with no silent waiver. Keep tools out of the runtime image, run trusted source builds with bounded resources, follow upstream remediation and obtain security-owner disposition before declaring the full security/release gate passed. Container images have not been built/scanned because Docker Hub requests failed.

## Remaining production risks

Private cloud storage/IAM/lifecycle, TLS/proxy behavior, actual alert delivery, managed backup cadence and production log retention are unverified. Prompt-pattern sanitization has false-positive/false-negative limitations and is not a sandbox for arbitrary code. The application does not execute document instructions as tools. External model privacy, legal label review and measured unsupported-claim rates remain blocked.

Database superusers can modify audit records. Enforce least privilege and independent retention if tamper resistance is required. Revocation cleanup, account deletion, retention/legal hold and purge of historic object versions require an owner-approved policy. No irreversible purge or weakening of controls was performed.

No blanket “security passed” or “production ready” claim is made. The final source scan excludes ignored secrets, recovery keys, browser traces and generated artifacts; regex scanning has coverage limits and cannot replace managed secret scanning in CI.
