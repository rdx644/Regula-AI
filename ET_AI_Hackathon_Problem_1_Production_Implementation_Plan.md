# ET AI Hackathon — Problem 1
# Agentic Regulatory Compliance & Control Intelligence Platform
## Production-Grade Agent-Directed Implementation Plan

> **Status:** Implementation Blueprint  
> **Target:** F3 feature coverage + D2 solution depth, with evidence-based justification  
> **Primary source:** ET × Accenture AI Hackathon — Detailed Problem Statements  
> **Engineering hardening reference:** Vibe Coding a Real SaaS — The 15-Layer Playbook  
> **Implementation rule:** Plan → Review → Implement in small increments → Verify → Review diff → Record decisions

---

## 0. Mission

Build a production-grade, agentic banking regulatory compliance platform that maintains a continuously traceable relationship:

**Regulations → Obligations → Applicability → Internal Policies/Controls → Evidence → Testing → Gaps → Remediation → Ongoing Monitoring**

The platform must demonstrate that AI agents can ingest and understand regulatory material, understand a bank's internal control framework, map regulatory obligations to controls, assess control effectiveness using evidence, identify and prioritize gaps, recommend remediation, and analyze the impact of regulatory change.

The system must be demonstrable as a working prototype and must have a detailed structural architecture showing process flow, key actions, decisions, model usage, and feature coverage.

---

# 1. Governing requirements

## 1.1 Hackathon requirements

Problem 1 requires an agentic solution that:

1. Understands regulatory requirements.
2. Understands how requirements change over time.
3. Assesses internal bank controls.
4. Determines how controls address regulatory requirements.
5. Identifies gaps.
6. Suggests appropriate remedies.
7. Maintains traceability across the complete compliance lifecycle.

The problem's desirable feature set contains 14 capabilities:

1. Regulatory intelligence and knowledge ingestion
2. Regulatory change intelligence
3. Regulatory obligation extraction
4. Bank control-framework understanding
5. Regulatory-to-control mapping
6. Control effectiveness assessment
7. Evidence-based compliance assessment
8. Gap identification
9. Risk-based gap prioritization
10. Remediation recommendation engine
11. Autonomous regulatory impact analysis
12. What-if / simulation capability
13. Cross-regulation intelligence
14. Regulatory contradiction detection

### Required feature-depth interpretation

- **F1:** at least 3 listed features
- **F2:** at least 6 listed features
- **F3:** at least 8 listed features

Solution depth:

- **D1:** mostly structured/textual input; acceptable outputs in majority of situations
- **D2:** mostly structured/textual input; high degree of demonstrable reliability
- **D3:** highly heterogeneous multimodal input; high degree of demonstrable reliability

### Evaluation dimensions

The implementation must optimize for:

- Significance and relevance
- Innovation and originality
- Effective use of AI
- Technical complexity and execution
- Agentic/autonomous capability
- Business/user impact
- Prototype quality and usability
- Scalability, responsible AI and robustness

### Submission requirements

The final submission must demonstrate:

1. A working demo across all claimed capabilities.
2. Detailed structural architecture showing process flow, actions, decisions, model usage and key feature integration.

---

# 2. Target scope

## 2.1 Primary target

**Target position: F3 + D2**

This is an engineering target, not a claim to make before validation.

### F3 target

Implement at least 8 hackathon-listed features. Preferred target: **12/14**, provided quality remains high.

### D2 target

Use primarily structured and textual regulatory/internal-control inputs and demonstrate high reliability using a controlled evaluation dataset, citations, confidence thresholds, deterministic rules, human escalation and repeatable evaluation.

### D3 is out of initial scope

Do not claim D3 merely because OCR, images or multiple file types are technically accepted. D3 requires highly heterogeneous multimodal inputs **and** a high degree of demonstrable reliability.

---

# 3. Product definition

## 3.1 Product name

Working name:

**RegulaAI — Agentic Regulatory Compliance & Control Intelligence Platform**

The name may be changed later without affecting architecture.

## 3.2 Primary users

- Compliance Officer
- Regulatory Risk Analyst
- Internal Auditor
- Control Owner
- Compliance Manager
- Risk Manager
- Platform Administrator

## 3.3 Core product promise

> Convert regulatory documents into traceable obligations, map them to internal controls, evaluate evidence and effectiveness, prioritize compliance gaps, recommend remediation, and continuously analyze regulatory change impact.

## 3.4 Product non-goal

Do not build a generic regulatory chatbot.

The conversational interface is secondary. The core product is the **traceable compliance intelligence and control-assessment workflow**.

---

# 4. Core user journeys

## Journey A — New regulation

```text
Upload regulation
→ Validate file
→ Parse
→ Extract metadata
→ Extract obligations
→ Determine applicability
→ Map to controls
→ Identify evidence requirements
→ Assess control effectiveness
→ Identify gaps
→ Score risk
→ Generate remediation
→ Require human approval where necessary
→ Persist audit trail
```

## Journey B — Regulatory change

```text
New regulatory version
→ Version/diff analysis
→ Identify changed obligations
→ Reassess applicability
→ Identify affected controls
→ Reassess evidence
→ Recalculate gaps/risk
→ Generate impact assessment
→ Recommend remediation
→ Notify affected owners
```

## Journey C — Compliance investigation

```text
User question
→ Intent classification
→ Agent plan
→ Hybrid retrieval
→ Tool execution
→ Evidence validation
→ Grounded response
→ Source citations
→ Confidence
→ Audit trail
```

## Journey D — What-if simulation

```text
Scenario
→ Modify regulatory assumption
→ Determine affected obligations
→ Recalculate mappings/controls
→ Recalculate gaps
→ Recalculate risk
→ Estimate remediation impact
→ Produce scenario report
```

---

# 5. Feature coverage plan

| ID | Hackathon feature | Priority | Planned implementation |
|---|---|---:|---|
| F01 | Regulatory intelligence & knowledge ingestion | P0 | Document ingestion, metadata, versioning, hybrid retrieval |
| F02 | Regulatory change intelligence | P0 | Version comparison + semantic change detection |
| F03 | Regulatory obligation extraction | P0 | Structured LLM extraction + validation + citations |
| F04 | Bank control-framework understanding | P0 | Control/policy ingestion and normalization |
| F05 | Regulatory-to-control mapping | P0 | Candidate retrieval + rule checks + LLM reasoning |
| F06 | Control effectiveness assessment | P0 | Control test framework + evidence |
| F07 | Evidence-based compliance assessment | P0 | Evidence collection, validation, traceability |
| F08 | Gap identification | P0 | Obligation/control/evidence/test comparison |
| F09 | Risk-based gap prioritization | P0 | Deterministic scoring + explainability |
| F10 | Remediation recommendation engine | P0 | AI-generated, structured, human-approved plans |
| F11 | Autonomous regulatory impact analysis | P1 | Change → affected controls/gaps workflow |
| F12 | What-if / simulation capability | P1 | Scenario engine |
| F13 | Cross-regulation intelligence | P2 | Shared-obligation/control analysis |
| F14 | Regulatory contradiction detection | P2 | Potential conflict detection + human review |

### Minimum acceptance

Do not claim F3 unless at least 8 features are implemented, tested and demonstrated.

Preferred claim after verification: **12 features**.

---

# 6. Architectural principles

1. **Modular monolith first.**
2. Separate domain logic from UI and route handlers.
3. PostgreSQL is the system of record.
4. Object storage is private by default.
5. LLM output is never treated as authoritative without validation.
6. Regulatory assertions must be traceable to source evidence.
7. Deterministic rules are used wherever deterministic behavior is possible.
8. AI handles semantic interpretation, extraction, planning and explanation.
9. High-risk or low-confidence decisions require human review.
10. Every tenant-owned query is organization-scoped.
11. Every agent action is auditable.
12. Expensive/long-running work is asynchronous.
13. Every external integration is isolated behind an adapter.
14. No secrets in source code.
15. No direct production database edits.
16. Every schema change is a migration.
17. Every feature is implemented in small reviewable increments.
18. Never claim "done" with failing, skipped or hidden tests.

---

# 7. Reference architecture

```mermaid
flowchart TD
    USER[Compliance User]

    subgraph PRESENTATION[Presentation]
        WEB[Next.js Web Application]
        DASH[Compliance Dashboard]
        CHAT[Investigation Interface]
    end

    subgraph API[Application API]
        AUTH[Authentication / RBAC]
        API[FastAPI API Layer]
        VALID[Validation]
        POLICY[Authorization]
    end

    subgraph ORCHESTRATION[Agent Orchestration]
        SUP[Supervisor / Workflow Orchestrator]
        PLAN[Planner]
        VERIFY[Result Validator]
        HITL[Human Approval Gate]
    end

    subgraph AGENTS[Domain Agents]
        RI[Regulatory Intelligence]
        OBL[Obligation Extraction]
        APP[Applicability]
        CTRL[Control Framework]
        MAP[Control Mapping]
        EVID[Evidence Assessment]
        TEST[Control Testing]
        GAP[Gap Analysis]
        RISK[Risk Prioritization]
        REM[Remediation]
        IMP[Impact Analysis]
        SIM[Simulation]
        CROSS[Cross-Regulation]
        CONTR[Contradiction Detection]
    end

    subgraph TOOLS[Agent Tools]
        PARSER[Document Parser/OCR]
        RETRIEVE[Hybrid Retrieval]
        SEARCH[Regulatory Search]
        DIFF[Version/Semantic Diff]
        RULES[Deterministic Rules Engine]
        CALC[Risk Calculator]
        STORAGE[Evidence Storage]
    end

    subgraph KNOWLEDGE[Knowledge Layer]
        PGV[(PostgreSQL + pgvector)]
        KG[Compliance Relationship Model]
        OBJECT[(Private Object Storage)]
    end

    subgraph PLATFORM[Platform Services]
        QUEUE[Job Queue]
        CACHE[Redis Cache]
        OBS[Observability]
        AUDIT[Audit Log]
    end

    USER --> WEB
    WEB --> API
    DASH --> API
    CHAT --> API

    API --> AUTH
    API --> VALID
    API --> POLICY
    API --> SUP

    SUP --> PLAN
    PLAN --> AGENTS
    AGENTS --> TOOLS
    TOOLS --> KNOWLEDGE

    SUP --> VERIFY
    VERIFY --> HITL
    HITL --> SUP

    API --> QUEUE
    API --> CACHE
    API --> OBS
    SUP --> AUDIT
    AGENTS --> AUDIT

    PGV --> KG
    OBJECT --> PARSER
```

---

# 8. Agent architecture

## 8.1 Supervisor / Orchestrator

Responsibilities:

- interpret request
- create workflow plan
- select agents/tools
- enforce workflow policy
- manage dependencies
- handle failures/retries
- invoke human approval
- persist execution trace
- validate final output

The orchestrator must not contain domain-specific logic that belongs in domain services.

## 8.2 Regulatory Intelligence Agent

Input:

- regulatory documents
- metadata
- source context

Output:

- regulator
- jurisdiction
- document type
- publication date
- effective date
- version
- superseded version
- applicable product/domain
- document status

## 8.3 Obligation Extraction Agent

Extract structured obligations:

```json
{
  "obligation": "...",
  "actor": "...",
  "requirement": "...",
  "condition": "...",
  "frequency": "...",
  "effective_date": "...",
  "source_document_id": "...",
  "source_section": "...",
  "source_page": "...",
  "confidence": 0.0
}
```

Every obligation must preserve source provenance.

## 8.4 Applicability Agent

Classify:

- applicable
- not applicable
- conditionally applicable
- uncertain / human review

Use structured bank/product/jurisdiction facts plus deterministic applicability rules where possible.

## 8.5 Control Framework Agent

Extract and normalize:

- control ID
- control objective
- control description
- owner
- frequency
- procedure
- evidence requirement
- business unit
- policy source

## 8.6 Mapping Agent

Workflow:

```text
Obligation
→ Candidate controls
→ Semantic similarity
→ Metadata/rule filtering
→ LLM reasoning
→ Confidence
→ Mapping state
```

Mapping states:

- mapped
- partially mapped
- unmapped
- conflicting
- human review

## 8.7 Evidence Agent

Verify:

- evidence exists
- evidence belongs to correct control
- evidence date is relevant
- evidence covers required period
- evidence is sufficiently complete

Never invent missing evidence.

## 8.8 Control Testing Agent

Run structured control tests against evidence and control requirements.

Output:

- effective
- partially effective
- ineffective
- unable to assess
- human review

## 8.9 Gap Agent

Compare:

```text
Obligation
vs
Applicability
vs
Control
vs
Evidence
vs
Test result
```

Produce a traceable gap record.

## 8.10 Risk Agent

The LLM explains risk but must not arbitrarily calculate it.

Use a deterministic scoring service.

Example conceptual factors:

```text
Regulatory severity
Business impact
Control weakness
Evidence deficiency
Exposure
```

The actual formula must be documented and configurable.

## 8.11 Remediation Agent

Produce structured plans:

- root cause
- recommended action
- control change
- owner recommendation
- priority
- target date
- evidence required
- validation test
- expected residual risk

Human approval is required before externally consequential remediation actions.

## 8.12 Impact Analysis Agent

For a new/changed regulation:

```text
Changed clauses
→ Changed obligations
→ Affected mappings
→ Affected controls
→ Affected evidence
→ Affected gaps
→ Risk changes
→ Remediation
```

## 8.13 Simulation Agent

Never mutate authoritative records during simulation.

Use an isolated scenario context.

## 8.14 Cross-Regulation Agent

Identify:

- common obligations
- overlapping controls
- duplicate requirements
- common evidence
- potential consolidation opportunities

## 8.15 Contradiction Agent

Only output:

**Potential contradiction**

unless verified by appropriate human/legal/compliance review.

---

# 9. AI architecture

## 9.1 Hybrid retrieval

Use:

```text
Metadata filtering
+
Keyword retrieval
+
Vector retrieval
+
Relationship retrieval
+
Reranking
```

Do not rely exclusively on vector similarity.

## 9.2 Source hierarchy

Prefer:

1. Original regulatory document
2. Approved internal policy/control document
3. Verified evidence
4. Structured database facts
5. Derived AI interpretation

## 9.3 Grounding requirement

Every regulatory conclusion must expose:

- source document
- section
- page where available
- extracted passage/reference
- confidence
- assessment status

## 9.4 AI output schema

All important agent outputs must use structured schemas.

No free-form parsing of critical agent responses.

## 9.5 Model fallback

External LLM providers must be accessed through a provider abstraction:

```text
LLMProvider
├── primary provider
├── fallback provider
└── deterministic fallback where applicable
```

Provider failures must not corrupt authoritative records.

---

# 10. Data architecture

## 10.1 Core entities

```text
Organization
User
Membership
RegulatoryDocument
RegulatoryVersion
RegulatoryObligation
BusinessUnit
Product
Policy
Control
ControlRequirement
RegulationControlMapping
Evidence
ControlTest
ComplianceAssessment
Gap
RiskAssessment
RemediationPlan
RegulatoryChange
ImpactAssessment
Simulation
AgentRun
AgentStep
ToolCall
AuditLog
```

## 10.2 Required tenant field

Every tenant-owned entity must contain:

```text
organization_id
```

and every query must enforce tenant scoping.

## 10.3 Common columns

```text
id UUID
created_at
updated_at
deleted_at where recovery/soft-delete is appropriate
organization_id where tenant-owned
```

## 10.4 Key indexes

Create indexes for:

- foreign keys
- organization_id
- status
- effective_date
- regulator
- risk level
- owner
- created_at
- workflow status
- frequently filtered combinations

## 10.5 File storage

Files:

- private by default
- uploaded using signed URLs where practical
- validated for type and size
- stored outside PostgreSQL
- represented in DB by metadata/object key
- downloaded only after authorization
- storage paths scoped by organization

---

# 11. Database schema draft

```text
organizations
users
organization_members

regulatory_documents
regulatory_versions
regulatory_obligations

business_units
products

policies
controls
control_requirements
regulation_control_mappings

evidence
control_tests

compliance_assessments
gaps
risk_assessments
remediation_plans

regulatory_changes
impact_assessments
simulations

agent_runs
agent_steps
tool_calls

audit_logs
notifications
```

Use PostgreSQL as the system of record.

Use pgvector for semantic retrieval where appropriate.

A graph database is not required for the initial implementation. Model relationships relationally first; add a dedicated graph system only if evaluation demonstrates a material benefit.

---

# 12. API architecture

## Public/application API conventions

Every endpoint must have:

- authentication check
- authorization check
- tenant scoping
- boundary validation
- standardized errors
- request ID
- structured logging
- tests

## Suggested endpoints

```text
GET    /api/health/live
GET    /api/health

POST   /api/regulations
GET    /api/regulations
GET    /api/regulations/:id
POST   /api/regulations/:id/process
POST   /api/regulations/:id/extract-obligations

GET    /api/obligations
GET    /api/obligations/:id

POST   /api/policies
POST   /api/controls
GET    /api/controls

POST   /api/mappings
GET    /api/mappings

POST   /api/evidence
GET    /api/evidence

POST   /api/assessments
GET    /api/assessments

GET    /api/gaps
GET    /api/gaps/:id
POST   /api/gaps/:id/analyze

POST   /api/remediation
GET    /api/remediation

POST   /api/regulations/compare
POST   /api/impact-analysis

POST   /api/simulations

POST   /api/investigations
```

Long-running operations must return a job/workflow identifier rather than blocking the HTTP request.

---

# 13. Asynchronous job architecture

Use a queue for:

- document parsing
- OCR
- embedding
- obligation extraction
- large evidence processing
- regulatory comparison
- impact analysis
- report generation
- notifications

Every job must be:

- idempotent
- retryable
- exponential-backoff enabled
- bounded by maximum retries
- observable
- traceable to organization and workflow

---

# 14. Frontend architecture

## Core screens

1. Executive Dashboard
2. Regulatory Library
3. Regulation Detail
4. Obligation Explorer
5. Control Library
6. Compliance Matrix
7. Evidence Center
8. Gap Center
9. Remediation Center
10. Regulatory Change Center
11. Impact Analysis
12. What-if Simulation
13. Investigation Assistant
14. Audit/Activity Trail
15. Admin/Settings

## Design system

Create reusable:

- buttons
- forms
- tables
- badges
- dialogs
- toasts
- skeletons
- empty states
- error states
- approval panels
- evidence/citation components
- confidence indicators

Every data-driven screen must handle:

- loading
- empty
- error
- success

The UI must work on desktop and at least 375px mobile width.

---

# 15. Compliance matrix

The central product screen should provide:

| Obligation | Applicability | Control | Evidence | Test | Effectiveness | Gap | Risk | Remediation |
|---|---|---|---|---|---|---|---|---|

Clicking any cell must preserve traceability back to the original source.

---

# 16. Human-in-the-loop policy

Mandatory review for:

- low-confidence obligation extraction
- uncertain applicability
- conflicting regulatory sources
- contradictory requirements
- high-impact compliance conclusions
- critical/high-risk remediation
- changes to authoritative compliance records
- external actions

AI can recommend.

Authorized users approve authoritative decisions.

---

# 17. Responsible AI controls

Implement:

### Grounding

No authoritative conclusion without source evidence.

### Confidence

Every AI-derived critical result gets a confidence value.

### Escalation

Low confidence → human review.

### Provenance

Every output references source records.

### Deterministic calculations

Risk scoring and policy constraints should be deterministic.

### No silent mutation

Agents cannot silently alter approved compliance records.

### Prompt-injection isolation

Documents are data, not instructions.

### PII/sensitive-data minimization

Do not place unnecessary sensitive information in prompts or logs.

### Model transparency

Store:

- model/provider identifier
- model configuration
- prompt/template version
- workflow version
- timestamp

---

# 18. Security architecture

## Threat model assets

- regulatory documents
- internal policies
- evidence
- user accounts
- organization data
- AI provider credentials
- audit records
- compliance findings

## Threat classes

- broken access control
- cross-tenant access
- injection
- XSS
- SSRF
- malicious file upload
- secret leakage
- prompt injection
- data exfiltration
- excessive AI usage
- denial of service
- insecure dependencies

## Required controls

- proven authentication provider
- RBAC
- server-side authorization
- organization scoping
- private storage
- signed URLs
- input validation
- file type/size validation
- rate limiting
- security headers
- secret management
- dependency scanning
- secret scanning
- structured/redacted logs
- audit logging

---

# 19. Prompt-injection defence

Treat every uploaded document and retrieved text as untrusted data.

Pipeline:

```text
Input document
→ Parse
→ Detect embedded instructions
→ Mark untrusted content
→ Sanitize/control context
→ Retrieve relevant evidence
→ Agent reasoning
```

The model must never be allowed to interpret regulatory document text as system-level instructions.

Test with adversarial documents containing:

- instruction override
- role change
- secret extraction
- tool abuse
- credential theft
- context poisoning
- encoded instructions
- indirect instructions

The firewall is not Problem 1's primary feature, but document-level prompt-injection resistance is a required security control for this agentic architecture.

---

# 20. Authentication and authorization

Recommended roles:

| Role | View | Upload | Assess | Remediate | Admin |
|---|---:|---:|---:|---:|---:|
| Owner | ✓ | ✓ | ✓ | ✓ | ✓ |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| Compliance Manager | ✓ | ✓ | ✓ | ✓ | — |
| Analyst | ✓ | ✓ | ✓ | — | — |
| Control Owner | scoped | evidence | scoped | scoped | — |
| Viewer | ✓ | — | — | — | — |

The exact permission matrix must be stored in `/docs/permissions.md`.

All permissions are enforced server-side.

---

# 21. Observability

## Structured logs

Every request/agent execution should contain:

```text
request_id
workflow_id
agent_run_id
organization_id
user_id where appropriate
operation
status
latency
model/provider where appropriate
```

Never log:

- passwords
- API keys
- access tokens
- authorization headers
- unnecessary sensitive evidence
- raw confidential content

## Metrics

Track:

- API latency
- p95/p99 latency
- error rate
- document-processing time
- agent execution time
- queue depth
- job failure rate
- retrieval latency
- LLM latency
- token consumption
- AI cost
- extraction accuracy
- mapping accuracy
- human-review rate
- unresolved gaps
- remediation completion

---

# 22. Rate limiting and AI cost protection

At minimum:

```text
Authentication endpoints:
strict IP + account limits

Document processing:
per-organization limit

AI investigation:
per-user + organization limit

Impact analysis:
per-organization limit

General API:
per-user limit
```

Implement:

- shared rate-limit store
- 429 responses
- Retry-After
- per-org AI quotas
- daily/monthly token usage
- global spending cap
- usage dashboard
- 80% quota alert

---

# 23. Caching

Cache only where safe.

Candidates:

- public/static assets
- regulatory metadata
- non-sensitive repeated retrieval
- expensive deterministic calculations where invalidation is clear

Tenant data cache keys must include:

```text
organization_id
```

Authenticated responses must not be exposed through shared public caching.

Never cache authoritative compliance results without an explicit invalidation strategy.

---

# 24. Testing strategy

## 24.1 Unit tests

Test:

- risk calculation
- applicability rules
- obligation schema validation
- mapping rules
- permission logic
- confidence policy
- state transitions
- scenario isolation

## 24.2 Integration tests

Test:

- API + database
- auth + authorization
- document ingestion
- retrieval
- agent tools
- evidence pipeline
- remediation persistence
- regulatory versioning

Use a real test PostgreSQL database.

## 24.3 E2E tests

Critical path:

```text
Login
→ Create/select organization
→ Upload regulation
→ Process
→ Extract obligations
→ Upload controls
→ Map
→ Upload evidence
→ Assess
→ Generate gaps
→ Prioritize
→ Generate remediation
→ Compare regulatory version
→ Run impact analysis
→ Run simulation
```

## 24.4 Security tests

Explicitly test:

- cross-tenant resource access
- unauthorized role actions
- malformed uploads
- oversized uploads
- prompt injection
- XSS payloads
- SSRF paths if URL ingestion exists
- rate limits
- secret exposure
- insecure direct object references

---

# 25. AI evaluation framework

Create a golden evaluation dataset before claiming D2.

## Dataset

Include representative examples for:

- regulatory clauses
- obligation extraction
- applicability
- control extraction
- control mapping
- evidence assessment
- gap identification
- risk prioritization
- remediation
- change impact
- contradictions

## Metrics

### Extraction

- precision
- recall
- F1

### Mapping

- precision
- recall
- false-positive rate

### Retrieval

- retrieval recall
- source relevance
- citation correctness

### Grounding

- claim-to-source support rate
- unsupported conclusion rate

### Agent performance

- workflow completion rate
- tool-selection correctness
- invalid-action rate
- escalation correctness
- recovery rate

### Reliability

Run the same benchmark repeatedly and report consistency.

---

# 26. Evaluation gates for D2

Do not claim high reliability merely because the demo works.

D2 readiness requires:

- benchmark dataset
- documented test methodology
- measurable results
- citation validation
- low unsupported-claim rate
- controlled human-review behavior
- repeatable outputs where deterministic behavior is expected
- failure-mode testing
- adversarial testing

The exact numeric thresholds must be established after the benchmark is built rather than invented upfront.

---

# 27. Regulatory change engine

## Versioning model

Every regulatory document must support:

```text
document
→ version
→ effective date
→ supersedes
→ superseded by
```

## Change detection

Use:

1. structural diff
2. textual diff
3. semantic diff
4. obligation-level diff

Classify:

```text
Added
Removed
Modified
Unchanged
Potentially conflicting
```

## Impact graph

```text
Changed obligation
→ mappings
→ controls
→ evidence
→ assessments
→ gaps
→ risks
→ remediation
```

---

# 28. What-if simulation architecture

Simulation must operate on a **scenario snapshot**.

Never modify production/authoritative records.

```text
Current State
→ Clone logical state
→ Apply scenario assumption
→ Re-run affected calculations
→ Compare with baseline
→ Produce impact
→ Discard scenario state
```

Output:

- baseline
- scenario
- changed obligations
- affected controls
- new/removed gaps
- risk delta
- remediation delta

---

# 29. Auditability

Every meaningful state transition must be recorded.

Example:

```text
USER:
Compliance Manager

ACTION:
Approved obligation OBL-102

SOURCE:
regulation-17.pdf, section 4.2

PREVIOUS STATE:
AI extracted / pending review

NEW STATE:
Approved

WORKFLOW:
WF-00931

TIMESTAMP:
...

MODEL:
...

REVIEWER:
...
```

Audit logs should be append-only from the application perspective.

---

# 30. Error handling

Standardize API errors:

```json
{
  "error": {
    "code": "REGULATION_PROCESSING_FAILED",
    "message": "The regulatory document could not be processed.",
    "request_id": "..."
  }
}
```

Never expose stack traces to users.

Agent failures should produce:

- user-friendly state
- retry option
- technical log
- workflow failure reason
- recovery path

---

# 31. Background job failure policy

Every job:

```text
PENDING
→ RUNNING
→ SUCCEEDED

or

RUNNING
→ RETRYING
→ FAILED
```

Store:

- attempt count
- last error
- next retry time
- workflow ID
- organization ID
- input reference
- output reference

No silent failures.

---

# 32. CI/CD

## Pull request pipeline

```text
Install
→ Lint
→ Format check
→ Typecheck
→ Unit tests
→ Integration tests
→ Security/dependency scan
→ Build
```

## Deployment

```text
PR
→ Preview
→ Review
→ Merge
→ Staging
→ Smoke test
→ Manual production approval
→ Production
```

## Git rules

- feature branches
- small commits
- Conventional Commits
- no direct main pushes
- no secrets
- PR review required

---

# 33. Environment model

Maintain:

```text
local
staging
production
```

Separate:

- databases
- storage buckets
- AI credentials
- auth configuration
- API keys
- monitoring environments

Provide `.env.example`.

Validate required environment variables at startup.

---

# 34. Hosting strategy

Use managed infrastructure.

Suggested initial deployment:

```text
Frontend:
Next.js → Vercel

Backend:
FastAPI → managed container platform

Database:
Managed PostgreSQL

Vector:
pgvector in PostgreSQL

Object storage:
Amazon S3 or equivalent

Queue/cache:
Managed Redis

Observability:
Sentry + platform logs
```

Do not introduce Kubernetes, service mesh or unnecessary microservices unless load testing or a concrete operational requirement justifies them.

---

# 35. Backup and recovery

Implement:

- automated DB backups
- retention policy
- object-storage versioning where appropriate
- restore procedure
- tested restore

Document:

```text
/docs/runbooks/backups.md
/docs/runbooks/restore.md
```

A backup is not considered verified until a restore has actually been performed.

---

# 36. Scaling strategy

Initial architecture should remain stateless.

Avoid:

- in-memory sessions
- in-memory job state
- local-only uploaded files
- in-memory distributed rate limits

Scale in this order:

```text
Measure
→ Database/index optimization
→ Background processing
→ Cache
→ Horizontal backend scaling
→ Worker scaling
→ Specialized services only if required
```

Load test the five most important endpoints and the complete core workflow.

Measure:

- p50
- p95
- p99
- error rate
- throughput
- bottleneck

---

# 37. Documentation structure

Required files:

```text
/AGENTS.md
/CLAUDE.md

/docs/
  system-design.md
  architecture.md
  api-conventions.md
  permissions.md
  testing.md
  ai-evaluation.md
  threat-model.md
  caching.md
  monitoring.md
  hosting.md

/docs/decisions/
  0001-stack.md
  0002-modular-monolith.md
  0003-data-model.md
  0004-agent-orchestration.md
  0005-ai-grounding.md
  ...

/docs/runbooks/
  deploy.md
  rollback.md
  backups.md
  restore.md
  incident.md
  agent-failure.md
  database-failure.md
```

---

# 38. AGENTS.md / CLAUDE.md mandatory rules

The project memory file must state:

```text
Project purpose
Hackathon requirements
Target F/D position
Approved stack
Architecture
Security rules
AI rules
Testing rules
Definition of done
Commands
Repository structure
Current implementation status
Known limitations
Architecture decisions
```

Mandatory coding rules:

```text
Never commit secrets.
Every endpoint validates input.
Every endpoint authenticates and authorizes.
Every tenant query is organization-scoped.
Every DB change is a migration.
Business logic stays out of route/UI layers.
Long-running work uses jobs.
AI outputs use schemas.
Critical AI outputs require provenance.
Never modify tests to hide implementation failures.
Run lint/typecheck/tests before declaring completion.
```

---

# 39. Agent-directed implementation protocol

Every coding task given to an AI coding agent must follow this exact protocol.

## Step 1 — Read context

Before modifying code, read:

```text
AGENTS.md
CLAUDE.md
relevant /docs files
current implementation
relevant tests
architecture decisions
```

## Step 2 — Produce a plan

Agent must state:

- files to modify
- files to create
- dependencies
- schema changes
- security impact
- tests required
- migration requirements
- risks

Do not code yet.

## Step 3 — Human review

Human reviews plan.

No implementation until plan is accepted.

## Step 4 — Implement small scope

One feature/vertical slice at a time.

## Step 5 — Verify

Run:

```text
lint
typecheck
unit tests
integration tests
relevant E2E tests
security checks
```

## Step 6 — Diff review

Agent reports:

```text
changed files
why changed
tests run
results
skipped items
mocks/stubs
hard-coded values
assumptions
known limitations
```

## Step 7 — Architecture record

If a decision changed, update:

```text
AGENTS.md / CLAUDE.md
/docs/decisions/
```

## Step 8 — Commit

Small, meaningful commit.

---

# 40. Agent definition of done

An agent must never say "complete" unless:

```text
[ ] Requirements implemented
[ ] Input validation implemented
[ ] Authentication checked
[ ] Authorization checked
[ ] Tenant isolation checked
[ ] Error handling implemented
[ ] Logging implemented
[ ] Tests added
[ ] Existing tests pass
[ ] Lint passes
[ ] Typecheck passes
[ ] Security implications reviewed
[ ] Documentation updated
[ ] No secrets added
[ ] No hidden mocks/stubs
[ ] No unreported hard-coded logic
```

---

# 41. Vertical implementation slices

Build in vertical slices instead of building every backend layer first.

## Slice 1 — Foundation

Deliver:

- repository
- auth
- organization
- RBAC
- DB
- migrations
- health check
- CI

## Slice 2 — Regulation ingestion

Deliver:

- upload
- parsing
- metadata
- document library
- storage
- processing job

## Slice 3 — Obligation extraction

Deliver:

- extraction agent
- structured schema
- citations
- confidence
- human approval

## Slice 4 — Control framework

Deliver:

- policy upload
- control extraction
- control library

## Slice 5 — Mapping

Deliver:

- candidate retrieval
- mapping agent
- mapping confidence
- approval

## Slice 6 — Evidence

Deliver:

- evidence upload
- evidence metadata
- evidence validation

## Slice 7 — Assessment

Deliver:

- control test
- effectiveness
- compliance assessment

## Slice 8 — Gaps

Deliver:

- gap generation
- gap dashboard
- deterministic risk score

## Slice 9 — Remediation

Deliver:

- recommendation
- approval
- assignment
- lifecycle

## Slice 10 — Change intelligence

Deliver:

- versioning
- diff
- changed obligations
- impact analysis

## Slice 11 — Simulation

Deliver:

- scenario
- isolated snapshot
- comparison
- report

## Slice 12 — Advanced intelligence

Deliver:

- cross-regulation
- contradiction detection

## Slice 13 — Production hardening

Deliver:

- observability
- security
- rate limiting
- caching
- backups
- load testing
- runbooks

## Slice 14 — Evaluation & demo

Deliver:

- benchmark
- metrics
- demo data
- final architecture
- evidence of F3/D2

---

# 42. Demo data strategy

Do not use random documents during the final demo.

Prepare a deterministic scenario dataset:

```text
Regulation A — Version 1
Regulation A — Version 2

Policy Set
Control Framework
Evidence Pack
Known Control Gaps
Expected Mapping Results
Expected Change Impact
```

Create a seeded organization containing:

- realistic users
- controls
- obligations
- evidence
- mappings
- known gaps
- remediation tasks

The final demo must be reproducible.

---

# 43. Final hackathon demonstration

## Scenario

A new regulatory version is uploaded.

### Demonstration sequence

1. Upload document.
2. Show regulatory metadata.
3. Extract obligations.
4. Show source citations.
5. Determine applicability.
6. Map obligations to controls.
7. Show unmapped/partial controls.
8. Upload/inspect evidence.
9. Test controls.
10. Generate compliance gaps.
11. Prioritize risks.
12. Generate remediation.
13. Upload changed regulatory version.
14. Show semantic changes.
15. Show affected obligations.
16. Show affected controls.
17. Show new gaps.
18. Run impact analysis.
19. Run what-if scenario.
20. Ask investigation question.
21. Show evidence-backed answer and audit trace.

---

# 44. Evaluation evidence dashboard

Create an internal "Hackathon Evaluation" page showing:

```text
Feature coverage:
12 / 14

Solution depth:
D2

Obligation extraction:
Precision / Recall / F1

Mapping:
Precision / Recall / F1

Grounded claims:
%

Citation correctness:
%

Agent workflow completion:
%

Human escalation accuracy:
%

Average workflow latency:
...

AI cost per assessment:
...

Security test status:
PASS
```

This gives judges concrete evidence rather than unsupported claims.

---

# 45. Innovation strategy

The innovation should not be "we used an LLM."

Differentiation:

1. **Traceable compliance graph**
2. **Regulation-to-control lifecycle**
3. **Evidence-aware control effectiveness**
4. **Autonomous regulatory impact analysis**
5. **Risk-based gap prioritization**
6. **Scenario simulation**
7. **Human-governed agentic decisions**
8. **Continuous regulatory version intelligence**
9. **Cross-regulation control reuse**
10. **Audit-ready agent execution trace**

---

# 46. What NOT to build

Out of scope unless explicitly required later:

- full banking core integration
- payment processing
- Kubernetes
- service mesh
- custom authentication
- custom LLM training
- fully autonomous legal decisions
- automatic external regulatory submissions
- autonomous production remediation
- unnecessary microservices
- custom vector database if pgvector is sufficient
- dedicated graph database unless proven necessary
- complex billing system
- multi-region active-active infrastructure

The goal is a robust, demonstrable architecture—not infrastructure theatre.

---

# 47. Production-hardening checklist

## System design

- [ ] Users and roles defined
- [ ] Core workflows defined
- [ ] Tenancy defined
- [ ] Data sensitivity documented
- [ ] Expected scale documented
- [ ] Non-functional requirements documented
- [ ] Out-of-scope documented

## Architecture

- [ ] Modular architecture
- [ ] Architecture diagram
- [ ] ADRs
- [ ] Background jobs
- [ ] External service adapters

## Database

- [ ] PostgreSQL
- [ ] Migrations
- [ ] Indexes
- [ ] Constraints
- [ ] Tenant isolation
- [ ] Backups
- [ ] Restore test

## Auth

- [ ] Proven auth provider
- [ ] RBAC
- [ ] Server authorization
- [ ] Cross-tenant tests
- [ ] Session management

## Backend

- [ ] Input validation
- [ ] Standard errors
- [ ] Pagination
- [ ] Idempotency
- [ ] Background jobs
- [ ] Retries
- [ ] Timeouts

## Frontend

- [ ] Design system
- [ ] Loading states
- [ ] Empty states
- [ ] Error states
- [ ] Accessibility
- [ ] Mobile compatibility
- [ ] No secrets in client bundle

## CI/CD

- [ ] Lint
- [ ] Typecheck
- [ ] Unit tests
- [ ] Integration tests
- [ ] Security scanning
- [ ] Preview deployment
- [ ] Staging
- [ ] Production approval
- [ ] Rollback

## Security

- [ ] Threat model
- [ ] Secret scan
- [ ] Dependency audit
- [ ] Prompt injection tests
- [ ] Upload security
- [ ] Security headers
- [ ] Rate limiting
- [ ] Log redaction

## AI

- [ ] Structured outputs
- [ ] Source citations
- [ ] Confidence
- [ ] Human escalation
- [ ] Deterministic risk engine
- [ ] Prompt/version tracking
- [ ] Golden dataset
- [ ] Evaluation metrics
- [ ] Agent audit trail

## Operations

- [ ] Structured logs
- [ ] Error tracking
- [ ] Health checks
- [ ] Metrics
- [ ] Alerts
- [ ] Runbooks
- [ ] Cost monitoring
- [ ] AI quota

## Scale

- [ ] Load testing
- [ ] Query optimization
- [ ] Pagination
- [ ] Stateless backend
- [ ] Connection pooling
- [ ] Worker scaling strategy

---

# 48. Final acceptance criteria

The project is ready for hackathon submission only when:

### Functional

- [ ] Complete core compliance workflow works.
- [ ] At least 8 hackathon features are implemented.
- [ ] Preferred 12-feature target is demonstrable.
- [ ] Regulatory change workflow works.
- [ ] Evidence-based assessment works.
- [ ] Risk prioritization works.
- [ ] Remediation works.
- [ ] What-if simulation works if claimed.

### Agentic

- [ ] Agents reason over structured evidence.
- [ ] Agents select/use tools.
- [ ] Agent workflows are observable.
- [ ] Agents can recover from transient failures.
- [ ] Human approval exists for high-impact decisions.
- [ ] No hidden manual work is presented as autonomous behavior.

### Reliability

- [ ] Golden evaluation dataset exists.
- [ ] Metrics are measured.
- [ ] Citations are verified.
- [ ] Unsupported claims are measured.
- [ ] Failure cases are documented.

### Security

- [ ] Cross-tenant access is blocked.
- [ ] Uploaded files are protected.
- [ ] Prompt injection is tested.
- [ ] Secrets are protected.
- [ ] Logs are redacted.
- [ ] Rate limits exist.

### Production

- [ ] CI passes.
- [ ] Staging exists.
- [ ] Production deployment works.
- [ ] Backups exist.
- [ ] Restore tested.
- [ ] Monitoring exists.
- [ ] Runbooks exist.

### Submission

- [ ] Working demo is reproducible.
- [ ] Architecture diagram is complete.
- [ ] Feature/depth claim is evidence-backed.
- [ ] Demo covers every claimed feature.
- [ ] Limitations are explicitly disclosed.
- [ ] No feature is claimed merely because a stub exists.

---

# 49. Final implementation sequence

```text
PHASE 0
Project memory + requirements lock
        ↓
PHASE 1
System design + ADRs
        ↓
PHASE 2
Architecture + repository scaffold
        ↓
PHASE 3
PostgreSQL + migrations + auth + RBAC
        ↓
PHASE 4
Regulatory document ingestion
        ↓
PHASE 5
Obligation extraction + citations
        ↓
PHASE 6
Internal controls + policies
        ↓
PHASE 7
Regulation ↔ control mapping
        ↓
PHASE 8
Evidence + control testing
        ↓
PHASE 9
Gap + deterministic risk engine
        ↓
PHASE 10
Remediation
        ↓
PHASE 11
Regulatory change intelligence
        ↓
PHASE 12
Autonomous impact analysis
        ↓
PHASE 13
What-if simulation
        ↓
PHASE 14
Cross-regulation + contradiction intelligence
        ↓
PHASE 15
Evaluation benchmark
        ↓
PHASE 16
Security + observability + rate limits
        ↓
PHASE 17
CI/CD + staging + production
        ↓
PHASE 18
Load testing + reliability validation
        ↓
PHASE 19
Final seeded demo
        ↓
PHASE 20
Hackathon submission evidence
```

---

# 50. Agent execution contract

Use the following instruction as the standard operating contract for any coding agent working on this repository:

> **You are an implementation agent for the ET AI Hackathon Problem 1 project.**
>
> Before changing anything, read `AGENTS.md`, `CLAUDE.md`, the relevant `/docs` files, architecture decisions, existing implementation and tests.
>
> Do not invent requirements. The hackathon problem statement is the product requirement source; the approved system-design and architecture documents constrain implementation.
>
> Work only on the requested scope.
>
> First provide an implementation plan. Do not write code until the plan is approved.
>
> Implement the smallest production-quality vertical slice that satisfies the requirement.
>
> Follow all architecture, security, tenancy, validation, authorization, AI-grounding and testing rules.
>
> Never put business logic in UI components or route handlers.
>
> Never trust client-side authorization.
>
> Never allow cross-tenant access.
>
> Never treat unverified LLM output as authoritative compliance truth.
>
> Every regulatory claim must preserve provenance.
>
> Use deterministic logic wherever deterministic behavior is possible.
>
> Long-running work must use background jobs.
>
> All schema changes must use migrations.
>
> Never commit secrets.
>
> After implementation, run lint, typecheck, unit tests, integration tests and relevant E2E/security tests.
>
> Before declaring completion, report:
>
> 1. Files changed and why.
> 2. Tests executed and exact results.
> 3. Anything skipped.
> 4. Anything mocked.
> 5. Anything hard-coded.
> 6. Assumptions made.
> 7. Known limitations.
> 8. Security implications.
> 9. Architecture decisions introduced.
>
> Do not describe work as complete if tests are failing, skipped without justification, or if required functionality is stubbed.

---

# 51. Governing principle

The system must be built according to this hierarchy:

```text
Hackathon Problem Statement
        ↓
Approved System Design
        ↓
Approved Architecture
        ↓
Domain/Data Contracts
        ↓
Implementation
        ↓
Automated Verification
        ↓
Security Verification
        ↓
AI Evaluation
        ↓
Production Hardening
        ↓
Hackathon Demonstration
```

**The implementation must never move upward by bypassing verification.**

The final product should demonstrate not merely that AI can answer regulatory questions, but that a controlled agentic system can transform regulatory change into a traceable, evidence-backed, risk-prioritized and human-governed compliance workflow.
