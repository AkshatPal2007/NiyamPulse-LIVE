# Paste this entire message into Codex (in the EXISTING NiyamPulse repository)

You are the lead engineer migrating the existing NiyamPulse codebase from its old PDF-first scholarship-amendment concept to **NiyamPulse v2: a mass-user, personalized Indian exam-notification platform**, for school students and engineering aspirants. **This is the user's decided product direction. Do NOT continue building the upload-first scholarship app as the core experience.**

I am developing on **Windows native, Python 3.12**, with a React/TypeScript frontend if one already exists. No Docker/WSL requirement. I have supplied a migration kit containing:
- `AGENTS.md`, `SHARED_CONTRACTS.md`, `PROGRESS.md`
- `backend/schemas.py`, `backend/legacy_schemas_v1.py`
- `config/exam_catalog.json`, `config/source_registry.json`
- `docs/EXAM_SOURCES.md`, `tests/test_schema_contracts.py`
- `MIGRATION_README.md`, `requirements-contracts.txt`.

### FIRST: inspect, do not destroy

1. Inspect existing `git status`, project tree, `AGENTS.md`, backend/frontend framework, current `schemas.py` imports, routes, data stores, test suite, and any working components. Show a short **reuse / adapt / deprecate / missing** inventory. Preserve unrelated user changes. Do not run destructive git commands or delete files without asking.
2. Compare the kit against existing files, merge **deliberately**. Keep old v1 schema names operational via the legacy shim, or provide a better compatibility strategy with tests. Do not replace working deterministic eligibility code with LLM calls.
3. Run Windows Python 3.12 smoke checks and existing tests; report exact commands and results. Fix import and contract errors before progressing.
4. Update `PROGRESS.md` with what you genuinely found and implemented, rather than assuming the new kit is running app code.

### PRODUCT YOU MUST BUILD

A user creates an account or uses a clearly labeled local demo login, selects **multiple** exams and cycles (JEE Main, NEET UG, NDA/NA, GATE, SSC JE, UPSC Engineering Services, plus expandable JEE Advanced, CUET UG, RRB JE, etc.), and receives **automatic in-app alerts** when an official monitored website posts a relevant notice. No recurring manual PDF upload by end users. User may optionally provide marks, age, income, etc. for supported deterministic impact detection; these fields are opt-in and not required to subscribe. The app never claims to know official application status; `APPLIED_SELF_REPORTED` is self-reported.

**Main user experience**: searchable multi-exam catalog → subscriptions by exam year/session and topics → personalized notification feed with verified source reference, original notice link, concise Hindi/English summary, and possible impact. **Main admin experience**: official-source health → newly discovered notice queue → review/approval/quarantine → automatically matched recipients → delivered/read counts, matched-per-exam charts and audit evidence. Admin is OUR platform operator, not an SSC/NTA official.

**Important: most notices are informational** (registration dates, admit card, syllabus, result). Deliver these to correctly subscribed users without forcing an eligibility assessment. Only validated amendments to these five types may drive deterministic status changes: minimum marks, maximum income, application deadline, age bounds, required documents. For ambiguous or unsupported exam criteria, show `UNKNOWN` or `CONFLICT`, never an invented PASS/FAIL or official approval.

### IMPLEMENT IN INCREMENTS, WITH A WORKING VERTICAL SLICE FIRST

**Phase A — contracts/catalog/subscriptions/inbox:** Integrate supplied v2 contracts and JSON catalog. Build SQLite data tables/migrations, actual catalog endpoints, subscribe/unsubscribe, own in-app inbox, mark-read. Build basic student user UI and admin counters (real DB queries). Add unit/integration tests. Do not hardcode SSC CGL as the one active exam.

**Phase B — real monitoring:** Implement at least **two tested official listing adapters from different publishers** (prefer NTA JEE Main and GATE 2027 or UPSC NDA/ESE), with last-success/failure, configurable intervals, canonical URL/content SHA-256 duplicate detection, conservative HTTP handling, immutable snapshots, and robust year/session routing. Source registry currently contains official listing candidates but ALL are `enabled=false`; only enable individually after successful real tests and appropriate site-use review. Do not assume RSS or public APIs. Do not bypass anti-bot measures, CAPTCHA or rate limits. The source watcher must run while the frontend is closed (e.g., separate process), not only in a page component.

**Phase C — reviewed notice publication + matching:** SourceGate checks exact configured source/reference/authority/date, treats unknown as quarantine or review; manual review before an update is published for MVP. Use Sarvam where appropriate to extract typed notice facts with literal evidence and preserve effective dates. Deterministically route approved updates to subscriptions by `cycle_id` and `topics`, persist recipient matches, dispatch deduplicated in-app notifications. Only invoke pure Python rule evaluator for actual supported, evidence-backed rule amendments and users with sufficient opted-in profile data. No per-subscriber LLM calls.

**Phase D — Sarvam and demo polish:** Add real Sarvam-105B structured extraction, Sarvam Vision OCR for scanned Indic pages, optional Saaras voice question and Bulbul Hindi audio with numeric/date checks; caching/offline replay labels. React UI should clearly show two audiences (school & engineering) and operator analytics. Demonstrate an incoming official notice or labeled fixture, review, fanout to subscribed synthetic users, and user inbox notification within 90 seconds. Don't display unmeasured claims.

### ENGINEERING GUARDRAILS

- Use `SHARED_CONTRACTS.md` and Pydantic v2 DTOs as the frontend/backend handshake, and align OpenAPI. Add `/api/v2`; preserve working `/api/v1` until migration complete.
- Native Windows 3.12; SQLite, FastAPI, pathlib, strict types, robust timeout/retry; avoid Docker/Redis/Celery dependency for MVP. Existing frontend choice may be retained if coherent; don't rewrite UI for fashion.
- Source allowlist, SSRF/redirect checks, robots/site restrictions, bounded download size, URL/hash dedup, no official application automation.
- Never display real user counts before real database records; seed synthetic demo users and prominently label them. Never claim source authenticity from hostname alone. Every published alert links to original official source.
- Protect minors: default subscriptions need no DOB/sensitive details; opt-in profile only; account ownership, deletion and privacy controls before public use.
- No fabricated accuracy scores, test passes, real-time monitoring or notification delivery. Distinguish planning, scaffold, implemented, and tested.
- Keep `PROGRESS.md` up-to-date as you edit. Commit in logical steps only when user permits. Do not silently launch paid services or large API usage.

### FIRST RESPONSE / FIRST IMPLEMENTATION EXPECTATIONS

First briefly report the existing repository audit and migration plan, then **start making actual code changes in the same task**. Prioritize phase A end-to-end with working requests and UI. Run tests and show pass/fail results, then list exactly what is still stubbed and the next smallest step for Phase B. Ask questions ONLY if essential missing credentials/files make progress impossible. Use safe local fixtures and mocks (clearly labeled) while live API access is unavailable. Never say monitoring is working until you observe a real fetched notice.
