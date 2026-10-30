# AGENTS.md — NiyamPulse LIVE

> Operating instructions for coding agents and human contributors. Read this file, then `SHARED_CONTRACTS.md`, then `PROGRESS.md` **before changing code**.
>
> Repository status: **contracts-only bootstrap**. Do not describe the app as implemented or working until its code and tests exist.

## 1. Mission

Build **NiyamPulse LIVE**, a visual, multilingual amendment-monitoring and decision-impact system for Indian scholarship notices. A source-linked amendment enters a watched intake; a reviewed amendment updates a closed set of rules; a **deterministic** Python engine recalculates affected applicant profiles; the frontend shows changed decisions as an animated shockwave, with evidence and accessible Hindi explanation.

The live demo must communicate in 10 seconds: **“One notice changed; here is exactly who was affected.”** No slides. A 90-second judge demonstration must work from reproducible synthetic data.

### Core product journey

1. Watch a configured local intake directory (first MVP), not an imaginary nationwide monitor.
2. Detect a new PDF; record its SHA-256 and acquisition metadata.
3. Extract text using PyMuPDF; use Sarvam Vision when needed for scanned/Indic pages.
4. Use Sarvam-105B to propose *structured candidate rules*, never decisions.
5. Check literal evidence, source lineage, dates, and amendment relationships; quarantine ambiguity or provenance failures.
6. Require explicit human review before applying an amendment.
7. Use pure Python for rule evaluation and before/after impact calculations.
8. Animate only actual changed profile states; reveal original and amended source passages.
9. Explain results in Hindi (optional Saaras input and Bulbul output) using verified facts and a numerical/date guard.
10. Display a measured scorecard only after real tests run on a **declared synthetic** dataset.

## 2. Non-negotiable invariants

- **LLM is not the authority.** It may extract candidates and translate/express facts; it must never assign PASS, FAIL, UNKNOWN, or CONFLICT.
- **Exactly five rule types in v1:** `minimum_marks`, `maximum_income_inr`, `application_deadline`, `age_bounds`, `required_documents`.
- **Exactly four rule/decision statuses:** `PASS`, `FAIL`, `UNKNOWN`, `CONFLICT`. “Eligible” and “approved” are not output statuses.
- Every operative rule needs **literal evidence** with `document_id`, `document_sha256`, `extraction_id`, 1-based `page_number`, and `literal_quote`.
- **Evidence presence is not verification.** The service must check the literal quote against its immutable extraction; verify numeric/date agreement; resolve clause scope and source lineage before a change can apply.
- A `MATCHED_CONFIGURED_SOURCE` result is *not* cryptographic authenticity. Avoid claiming that suspicious documents are proven forgeries.
- Unverified/contradictory amendments are **quarantined or held for review**. Do not silently mutate active rules, alerts, or stored decisions.
- The system must not claim official scholarship approval. Keep `Decision support only; not official approval.` visible in applicant results and voice/transcript views.
- **No invented metrics.** UI evaluation values must come from actual persisted evaluation runs; label synthetic datasets and baseline configurations.
- Never fabricate a successful Sarvam API call, monitoring state, screenshot, source highlight, or TTS outcome. Offline replay must be explicitly labeled.
- Never use production applicant PII in screenshots or benchmark fixtures. Demo applicants must be synthetic.

## 3. Technology and environment

**Development OS:** native **Windows 10/11**, PowerShell, **Python 3.12** (not WSL), Node.js LTS for the UI.

- Frontend: React + TypeScript + Vite + Tailwind CSS; small CSS transitions for the shockwave.
- Backend: Python 3.12, FastAPI, Pydantic **v2**, PyMuPDF, SQLite; `watchdog` for local intake.
- Sponsor: Sarvam Vision (OCR where needed), Sarvam-105B (structured candidate extraction), Saaras v4 (short speech input), Bulbul v4 Flash (guarded speech output).
- Do **not** add LangGraph, FAISS, Redis, Docker, Kubernetes, or Failproof AI by default. Add an external component only when it solves a demonstrated problem in the product's critical path.
- Monetary amounts: integer INR (not float). Marks: percentage in 0–100. Dates: ISO `YYYY-MM-DD`. API timestamps: timezone-aware ISO 8601 (use UTC `Z` when emitted). Scholarship date semantics: date-only rules in the relevant local calendar, default `Asia/Kolkata` for the demo; do not silently reinterpret deadlines in UTC.
- Use local caches keyed by content hash and extraction/model version, *not* filenames alone.

### Native Windows setup (PowerShell)

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "pydantic>=2.9,<3"
python -m backend.schemas
```

If activation is blocked by a PowerShell execution policy, skip activation and run commands with `.\.venv\Scripts\python.exe` directly. **Do not** change machine-wide execution policy merely for this project.

**Later, after `backend/main.py` exists**, install FastAPI and launch with:

```powershell
python -m pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1"
python -m uvicorn backend.main:app --reload --port 8000
```

These latter commands are a *future target*, not instructions that can launch the current contracts-only starter.

## 4. Repository conventions

Planned layout (only the four contract files exist in the initial delivery):

```text
niyampulse/
├── AGENTS.md
├── SHARED_CONTRACTS.md
├── PROGRESS.md
├── backend/
│   ├── schemas.py           # source-of-truth Pydantic v2 DTOs (exists)
│   ├── main.py              # future FastAPI application
│   ├── services/            # intake, extraction, gate, versioning, evaluator, explanations
│   └── tests/               # pure-engine, contracts, provenance, API tests
├── frontend/                # future React/Vite app
├── datasets/synthetic/      # future source PDFs, gold labels, personas
└── eval/                    # future reproducible benchmark runner and reports
```

- All HTTP JSON payloads must conform to `backend/schemas.py` and `SHARED_CONTRACTS.md`.
- The frontend must not invent counters, inferred eligibility, source provenance states, or status colors. Render returned typed data.
- API response models should use FastAPI `response_model` so invalid server payloads fail visibly.
- Store source PDFs immutably; store their extraction records and page anchors separately.
- Use consistent ID strings and document hashes; `SourceEvidence.page_number` is **1-based**; boxes are normalized `[0,1]`, origin top-left.
- Backend rule evaluation, precedence, gate checks, and numerical guards must each be independently testable pure functions where possible.
- Poll the event endpoint for the first version. Don't build a real-time WebSocket stack unless polling fails to meet the visual/demo requirement.
- Apply changes atomically with optimistic `expected_workspace_revision` to prevent stale overwrites.
- Errors must use `ApiError`, not arbitrary English exceptions returned in HTTP 200.

## 5. Rules of implementation

### Decision aggregation

For an applicant on a given date: unresolved conflict in a relevant effective rule → `CONFLICT`; otherwise any proven failing applicable condition → `FAIL`; otherwise any missing required value → `UNKNOWN`; otherwise all checked applicable conditions pass → `PASS`. If **no** applicable rules are verified, return `UNKNOWN`, not `PASS`. Preserve all per-rule checks and evidence.

### Amendment precedence

`ADD` adds a scoped rule; `REPLACE` targets one specific existing `rule_id`; `REVOKE` targets one existing `rule_id`. No global "latest PDF wins" shortcut. Effective ranges are **start-inclusive, end-exclusive**. Reject or hold for review ambiguous targets, incompatible scope, overlapping applicable rules, references pointing to another scheme, dates that fail chronology checks, and any unsupported condition type. A later unrelated amendment must not erase earlier changes.

### Change classification

Only overall `FAIL → PASS` is `IMPROVED`, and only `PASS → FAIL` is `WORSENED`. A transition involving `UNKNOWN` or `CONFLICT` that needs investigation is `REVIEW_REQUIRED`. Same overall status is `UNCHANGED`, even when a subordinate rule value changes; surface rule-level details separately. `changed` counts transitions where the **overall** status actually differs. Never turn a condition-level PASS into an official overall approval.

### Language / TTS

Construct a verified set of source-backed facts. Generate Hindi text through a controlled template or Sarvam-105B, then validate that its named rules, values, dates, and decision status match the engine output. **Block** audio when the guard fails; show the guarded template instead. Do not send unsupported sentences to the synthesizer.

## 6. Definition of done and tests

Before calling any feature finished:

- A failing test was written or reproduced, then passed after the change.
- At least one synthetic original + corrigendum pair runs through the actual parser/rule pipeline.
- Unsupported or unauthenticated document input cannot modify a committed rule set.
- `UNKNOWN` and `CONFLICT` are visibly distinct from `FAIL`.
- The animation reflects backend `ImpactEvent.transitions`, not hardcoded demo numbers.
- PDF evidence opens the correct page, with exact highlighting only when extraction coordinates are verified.
- Offline replay exercises the same local evaluator as online mode.
- UI distinguishes real live processing, cached extraction, and offline replay.
- A scorecard is not shown until a reproducible evaluation produced it.
- Tests run on **native Windows Python 3.12**, not only another developer's OS/Python version.

## 7. Agent collaboration and status updates

- Read `PROGRESS.md` first to avoid duplicating work or claiming planned files exist.
- Make small, reviewable commits and update `PROGRESS.md` with done/in-progress/blocked changes and test commands/results.
- If you change a public field, enum, endpoint, or default, update **both** `backend/schemas.py` and `SHARED_CONTRACTS.md` in the same change; consider whether to bump `SCHEMA_VERSION`.
- Separate **VERIFIED** (documented or observed), **ASSUMED** (design decision), and **UNTESTED** (needs proof) in technical notes.
- For external integrations, use environment variables; never commit `.env`, credentials, authentic documents containing sensitive data, audio samples with personal information, or internal API responses.
- If unsure, prefer one truthful working vertical slice over a partially mocked multi-screen product.
