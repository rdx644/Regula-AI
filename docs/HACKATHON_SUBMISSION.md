# RegulaAI: hackathon submission package

## Project

**RegulaAI — traceable regulatory compliance and control intelligence.**

Live demonstration: [regulaai-hackathon-web.onrender.com](https://regulaai-hackathon-web.onrender.com/).
Repository: [rdx644/Regula-AI](https://github.com/rdx644/Regula-AI).
Architecture: [interactive diagram](https://rdx644.github.io/Regula-AI/architecture/) and [implementation notes](../ARCHITECTURE.md).

## Submission description

RegulaAI brings regulatory sources, reviewed obligations, internal controls, private evidence, compliance tests and remediation into one tenant-scoped workspace. Reviewers can inspect source citations, approve mappings, assess deterministic findings and validate remediation with current evidence and a passing test. Durable jobs expose progress and failures; PostgreSQL records domain decisions and audit events.

The hackathon edition also compares exact text between parsed source versions, saves candidate impact drafts, runs isolated control-outage scenarios and answers guided questions using recorded workspace links and citations. The interface includes a brief Three.js introduction, reduced-motion support and accessibility checks.

This is a temporary synthetic-data prototype. Model execution is disabled by the owner's spending instruction. Prepared obligations are seeded examples; automated extraction tests use a disclosed synthetic adapter. Literal text comparison and guided investigation do not claim semantic legal reasoning. Real model accuracy, F3/D2 acceptance and durable production operations remain unverified.

## Five-minute judge demonstration

1. Open the live app. Allow a free service to wake up. Create a demonstration account using synthetic information and load **Demo scenario**.
2. In **Compliance matrix**, follow an obligation to its control, evidence and finding. Choose **Review source** to inspect its recorded quote/page. Explain that prepared records are synthetic examples.
3. In **Regulatory library**, upload `docs/demo/source-v1.txt` and show the actual parsing job and authenticated source download. AI extraction remains paused.
4. In **Control library**, propose and approve a control, link a reviewed obligation, upload synthetic evidence, inspect its source, review it as valid and record a passing manual test. Approve the mapping in **Compliance matrix**.
5. In **Gap & remediation**, approve and start the prepared action. Upload valid evidence to its linked control and record a passing test **after** starting the action. Complete validated remediation; reload to show persistence. Completion before validation is rejected.
6. In **Version comparison**, select the source uploaded in step 3. Upload `docs/demo/source-v2.txt`, wait for parsing and compare version 1 with version 2. Show exact before/after text and saved candidate impact scope. Select the prepared regulation instead if demonstrating linked candidate controls; use a synthetic revision of that source. Candidate scope requires human interpretation.
7. In **What-if scenarios**, select a mapped control, name a synthetic outage and run it. Show projected gaps and illustrative risk delta; the original control remains intact. Reload to show saved results.
8. In **Investigation & audit**, select control coverage or open gaps and run the guided query. Show recorded citations and the investigation audit event. Export the report if useful.

The guide is a demonstration sequence, not a claim that eight complete hackathon AI features have been validated. See the [acceptance matrix](SUBMISSION_READINESS.md).

## Demonstration inputs

- [Source version 1](demo/source-v1.txt) and [source version 2](demo/source-v2.txt): deliberately fictional text for literal comparison.
- [Evidence](demo/evidence.txt): synthetic review log; it is not real compliance evidence.
- The prepared Basel-themed scenario is user-specific and idempotent. Its stored ratios and confidence values are seeded, not evaluated predictions.

## Verified engineering scope

- 114 backend tests against isolated PostgreSQL/Redis; source comparison, audit and tenant-denial tests included.
- Five automated browser regression tests; actual parser/worker/storage/domain operations, with extraction alone replaced by a synthetic adapter.
- Frontend lint, TypeScript production build and tested accessibility/mobile paths.
- Live account/workspace/demo creation, private parsing/download, control/mapping/evidence/test review, gap execution, validated remediation closure, literal comparison, scenario worker and guided investigation/audit. Live axe and 390px checks pass across all eight workspace views.
- GitHub CI and Render Blueprint checks passed at feature revision `4d7c2ce`.
- Detailed receipts: [submission verification](evidence/hackathon-submission.json), [earlier frontend verification](evidence/frontend-redesign.json).

## Limitations to disclose

Free Render services can sleep; local uploaded files and queue data are ephemeral. Database lifetime is limited by the free hosting plan. Reupload synthetic sources after restarts if necessary. No real bank data should be used. There is no S3 dependency in the hackathon profile.

No paid provider call, golden prediction, real semantic change/impact evaluation, autonomous legal answer or externally published contest submission was made. Five previously disclosed high development-tool dependency findings remain open; runtime audit was clean at the earlier recorded check. Cloud recovery, monitoring delivery and production capacity are outside the verified demo scope.

## Owner submission fields

Use the description and links above. Supply your team names, contact information, competition-specific category and a recording of the live demonstration in the contest portal. Do not label the project production-certified or claim measured AI reliability. This package prepares the material; the owner submits it.
