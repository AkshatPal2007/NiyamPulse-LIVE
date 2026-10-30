# Copyable model handoff prompt

You are helping build **NiyamPulse LIVE** in
`C:\Users\Akshat\Desktop\Hackathon\ShipHappen` on native Windows / PowerShell /
Python 3.12. Read `AGENTS.md`, `SHARED_CONTRACTS.md`, `PROGRESS.md`, and `README.md`
before changing code. Inspect the implementation and run tests; distinguish
verified, assumed and untested behavior. Never describe planned features as working.

## Product and invariants

The product watches a configured local folder for Indian scholarship corrigenda,
extracts source-backed candidate rules, checks provenance/evidence, requires human
review, deterministically recalculates synthetic applicant decisions, and will
display actual decision changes as a visual impact wave. The demo message is:
"One notice changed; here is exactly who was affected."

Exactly five rule types: `minimum_marks`, `maximum_income_inr`,
`application_deadline`, `age_bounds`, `required_documents`. Exactly four decision
statuses: `PASS`, `FAIL`, `UNKNOWN`, `CONFLICT`. An LLM may propose candidates and
express verified facts; it must never determine decisions. Aggregate precedence
is CONFLICT > FAIL > UNKNOWN > PASS; no verified applicable rules means UNKNOWN.
Only overall FAIL to PASS is IMPROVED; only PASS to FAIL is WORSENED. Equal overall
status is UNCHANGED, even if individual checks change.

Preserve the visible disclaimer: **Decision support only; not official approval.**
Configured-source matching is not cryptographic authenticity. Evidence presence
alone is not verification. Demo applicants/notices are synthetic. Never invent
metrics, live monitoring, API success, highlights, OCR or audio.

## Completed and verified

**Phase 0:** `.venv` exists; native Windows Python 3.12.10 / Pydantic 2.14.2 verified.
Git exists. Check Git status before editing. Dependencies are in `requirements.txt`
and `requirements-dev.txt`. Local commits are made; do not infer they were pushed.

**Phase 1:** pure evaluators, reason codes, inclusive condition boundaries,
start-inclusive/end-exclusive effective intervals, scope matching, conflicts,
targeted ADD/REPLACE/REVOKE planning, content-bound verification inputs,
deterministic hashes, actual impact counts and PREVIEW events. Three English/Hindi
text fixture pairs cover 13 synthetic profiles with independent gold labels.
Core modules: `backend/services/rule_engine.py`, `amendments.py`, `impact.py`.

**Phase 2:** `backend/main.py` is a working local FastAPI backend. SQLite stores
immutable PDF bytes, extraction snapshots, acquisitions, committed snapshots and
events. Actual PyMuPDF extraction feeds a strict declared notice-template parser.
Source gates check configured acquisition, scheme/authority, original reference,
chronology, exact evidence identity and value/date/scope agreement. Unsupported or
unverified documents cannot change committed decisions. There is explicit
original review, amendment preview and human-confirmed application. Apply uses
one revision-checked transaction for review, rules, decisions, snapshot and event.
Concurrent applies have one winner; forced event-write failure rolls back the
whole operation. Multi-query workspace reads use one consistent snapshot.

Implemented `/api/v1` routes: health, workspace, PDF import, original review,
stored PDF/extraction access, amendment preview/apply, effective/known-at timeline,
and signed cursor event polling. Evaluation returns typed 404 until a real run
exists. Errors use `ApiError`; implemented JSON result routes use response models.

The Watchdog service actually detects stable new PDFs in a configured local
**corrigendum** directory, records hashes, suppresses duplicates and never applies
automatically. Health is observed. Extraction caches are labeled and keyed by PDF
hash plus extractor version. A supplied URL cannot establish trust. Duplicate
content preserves its first acquisition.

Public DTO/API version is **1.1.0**. `backend/schemas.py` is authoritative; update
it and `SHARED_CONTRACTS.md` together for public changes. Phase 1 engine version
remains 1.0.0. Internal rule/change trust hashes must never become client-controlled
HTTP flags. See `backend/services/README.md` for engine conventions.

**Verification:** 61 tests pass on Windows Python 3.12; schema smoke and pip check
pass. A real Uvicorn HTTP smoke verified health, workspace, actual local watcher,
docs and OpenAPI. Three synthetic PDFs were rendered with Poppler and visually
inspected. Full PDF/API fixture impact: 5 evaluated, 2 changed (1 improved,
1 review-required), 3 unchanged. These are test outcomes, not accuracy scores.
Starlette emits a non-failing httpx TestClient deprecation warning.

## Run locally

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m backend.demo_setup
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Swagger: `http://127.0.0.1:8000/docs`. Workspace: `scholarship-demo-2026`.
PDFs: `output/pdf/`. Watched folder: `var/intake/`. Setup creates configuration
and profiles only; it does not import, review or apply. See README for manual
review steps. Setup does not reset a used demo; choose another
`NIYAMPULSE_DATA_DIR` for isolation.

## Remaining work and limits

Next is the React + TypeScript + Vite + Tailwind frontend: command center,
source-review flow, four-status applicant grid, backend-event-driven impact wave,
timeline, quarantine presentation and page/quote evidence inspector. Generate
types from actual OpenAPI. Poll events and deduplicate IDs. Never infer decisions
or impact counts in TypeScript or animate a fabricated cohort.

There is no frontend yet. Sarvam Vision/105B/Saaras/Bulbul, guarded Hindi speech,
general free-form notice extraction, production authentication, exact PDF
coordinate highlighting, a 20+ pair benchmark/baseline and full product offline
replay remain unimplemented. Phase 2 PDF integration tests cover English;
Phase 1 text fixtures also cover Hindi. Scans visibly require OCR/review. Boxes
are empty: show page + literal quote until coordinates are verified. Do not add
LangGraph, Redis, Docker or other infrastructure without a demonstrated need.

Proceed only with the phase/task the user authorizes. Work autonomously within
scope, pause for required input, add meaningful failing regression tests before
fixing correctness behavior, update `PROGRESS.md` with exact commands/results,
and keep credentials and generated databases out of Git.
