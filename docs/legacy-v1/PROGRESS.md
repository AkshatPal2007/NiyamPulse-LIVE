# PROGRESS.md — NiyamPulse LIVE

**Last updated:** 30 October 2026  
**Primary track:** Culture Coded (Sarvam AI)  
**Development target:** Windows 10/11, native Python 3.12, PowerShell  
**Current milestone:** M2 — Local PDF backend verified; M3 frontend next

**Overall status:** 🟡 **PHASES 1–2 BACKEND IMPLEMENTED AND TESTED; FRONTEND AND SARVAM NOT IMPLEMENTED**

> This ledger prevents agents from mistaking a product plan for shipped software. Update it after each meaningful code change, with the exact tests and environment used. Demo numbers are synthetic fixtures until an actual evaluation script produces them.

## 1. Scope locked for v1

**Product:** NiyamPulse LIVE. A watched source brings a scholarship corrigendum; a source gate checks lineage; a human reviews; deterministic rules are revised; applicant statuses recalculate; an impact wave appears; each explanation links to literal evidence; optional Hindi speech makes the result accessible.

**Closed rules:** minimum marks, maximum annual household income (INR), application deadline, inclusive age bounds as of a specified date, required documents.

**Statuses:** `PASS`, `FAIL`, `UNKNOWN`, `CONFLICT` (no automatic official eligibility approval).

**Demo:** Synthetic original + corrigendum, controlled cohort, legitimate and unverified amendment, reproducible measured evaluation; 90-second no-slides flow with an offline replay fallback.

**Recommended app stack:** React/TypeScript/Vite/Tailwind frontend; Python 3.12 FastAPI/Pydantic 2/PyMuPDF/SQLite/Watchdog backend; Sarvam APIs for OCR/structured extraction/STT/TTS. Avoid extra orchestration infrastructure until needed.

## 2. What actually exists

| Artifact | State | Verification |
|---|---|---|
| `AGENTS.md` | ✅ Created | Instructions and repository conventions written |
| `SHARED_CONTRACTS.md` | ✅ Created | Endpoints, versioned payloads and trust/decision contract written |
| `backend/schemas.py` | ✅ Created | Pydantic v2 models, validators, discriminated rule union; JSON Schema generation smoke-checked |
| `PROGRESS.md` | ✅ Created | This coordination ledger |
| Native Windows / Python 3.12 run | ✅ Verified | Python 3.12.10 / Pydantic 2.14.2; 61 tests, schema smoke and pip check passed |
| FastAPI server and HTTP endpoints | ✅ M2 implemented | Real Uvicorn HTTP smoke and API tests; public schema 1.1.0 |
| React frontend and UI animations | ⬜ Not started | Wireframes/spec only |
| Document ingestion / local folder watcher | ✅ M2 implemented | Actual PyMuPDF extraction; Watchdog detects stable new local corrigenda, suppresses duplicates, reports observed health; no automatic apply |
| Sarvam API integration | ⬜ Not started | Sponsor endpoints not tested with actual credentials |
| SourceGate + provenance controls | ✅ M2 implemented for declared template | Literal/value/date/scope checks, configured acquisition, authority/scheme/reference/chronology checks, quarantine/manual-review holds; no authenticity certification |
| Amendment resolver / rule evaluator | ✅ M1 implemented | Five rule types, aggregation, effective windows, scoped conflicts, uncommitted ADD/REPLACE/REVOKE planning and PREVIEW impact |
| Source-highlighting inspector | 🟡 Evidence API ready | Stored PDF + exact page text/quote endpoints tested; frontend and exact boxes remain unimplemented |
| Hindi speech + numeric/date guard | ⬜ Not started | No live/cached audio created |
| Synthetic dataset / benchmark | 🟡 Initial fixtures only | Three English/Hindi text pairs, 13 synthetic profiles and independent gold outcomes; benchmark/scorecard not implemented |
| Demo run and offline replay | 🟡 Backend walkthrough ready | Synthetic PDF → extraction → gate → reviewed baseline/apply → persisted event tested; no frontend or full product replay yet |

### M1 artifacts added

- `backend/services/rule_engine.py`: deterministic rule checks, reason codes, aggregation, canonical content hashes and fail-closed verification inputs.
- `backend/services/amendments.py`: pure, uncommitted plans preserving unrelated rule history and rejecting ambiguous/incompatible/overlapping changes.
- `backend/services/impact.py`: backend-owned PREVIEW transitions/counts; never claims a committed apply.
- `backend/services/README.md`: trust boundary, function usage, verified behavior and assumed demo conventions.
- `backend/synthetic_demo.py` and `datasets/synthetic/phase1/`: strict fixture-only English/Hindi clause parser, measured text hashes/anchors, three pairs and 13 synthetic applicants.
- `backend/tests/`: 37 tests using standard-library unittest; no extra test dependency.
- `requirements.txt` and `.gitignore`: Pydantic v2 dependency range and exclusions for environments, credentials and generated caches. Previously tracked bytecode removed from version control.

### Local tooling check performed on this starter

- `python -m backend.schemas`: **passed** in the artifact-building environment.
- Pydantic JSON Schema generation for the main models: **passed** in the artifact-building environment.
- Environment used for the above: **Python 3.13.5**, **Pydantic 2.13.5**, **not Windows**.
- Do **not** treat these as a native Windows Python 3.12 compatibility certification.

### M1 native Windows verification — 30 October 2026

**VERIFIED:** native Windows, Python **3.12.10** (MSC AMD64), Pydantic **2.14.2**, using `.venv\Scripts\python.exe`.

```powershell
py -3.12 --version
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.synthetic_demo
```

- Schema smoke check: **passed**. JSON schemas generated successfully for all **34** Pydantic contract models.
- Test discovery: **37 passed**. Tests first failed on absent implementations; a maximum-date overlap regression was separately reproduced as a failing assertion and passed after the fix.
- Fixture replay: **passed** for all three pairs, matching independently authored gold outcomes across **13** synthetic profiles. Gold labels do not drive predictions.
- Marks relaxation: 5 evaluated, 2 changed (1 improved, 1 review-required), 3 unchanged.
- Hindi income tightening: 4 evaluated, 1 changed (1 worsened), 3 unchanged.
- Document expansion: 4 evaluated, 2 changed (1 worsened, 1 review-required), 2 unchanged.
- These are actual test-fixture results, **not** benchmark accuracy scores, official scholarship approvals or live-source processing.

**ASSUMED:** fixture target maps/effective dates and trust are curated test inputs. The engine accepts content-bound upstream attestations, not an evidence-presence shortcut. February 29 age handling and conservative scope-overlap policy are documented in `backend/services/README.md`.

**UNTESTED:** PDF parsing/OCR, production evidence and lineage gate, publication chronology, human review workflow, atomic persistence, watcher, API, frontend, Sarvam and full offline product replay. Text-file source hashes must not be described as PDF hashes. No HTTP field, enum, default or schema version changed.

### M2 implementation and verification — 30 October 2026

**VERIFIED:** native Windows Python **3.12.10**, Pydantic **2.14.2**, FastAPI **0.162.0**, Uvicorn **0.54.0**, PyMuPDF **1.28.2**, Watchdog **6.0.0**, python-multipart **0.0.32**, httpx **0.28.1**.

- `backend/main.py`: working health/workspace/import/original-review/preview/apply/PDF/extraction/timeline/events API, explicit localhost CORS and typed errors. HTTP 202 queues extraction; it never means approval.
- `backend/storage.py` and `backend/migrations/001_initial.sql`: SQLite bootstrap migration, immutable source/extraction/acquisition/snapshot/event records, content integrity checks, signed workspace-bound cursors and consistent read snapshots.
- `backend/services/pdf_intake.py`, `clauses.py`, `provenance.py`: real PDF extraction, strict notice grammar, literal page offsets, evidence for condition **and effective date**, exact candidate comparison, source lineage/authority/scheme/date gates. No OCR or inferred unsupported conditions.
- `backend/services/workspace.py`: source checks repeated within revision-checked `BEGIN IMMEDIATE` review/apply transactions. Review, rule history, decisions, snapshot and amendment event commit together or roll back together. Intake and previews never mutate active decisions.
- `backend/services/watcher.py`: actual stable-file Watchdog intake for local **corrigenda**; no auto-apply, content hash deduplication, read retries and observed runtime health. Original notices require explicit upload/review.
- `backend/demo_setup.py`, `backend/demo_fixtures.py`, `output/pdf/`: reproducible synthetic workspace/profiles and three actual PDFs (original, corrigendum, authority mismatch). Setup is idempotent and never imports/reviews/applies. The local `var/` data directory is ignored by Git.
- `README.md`: manual walkthrough and run commands. `MODEL_HANDOFF.md`: copyable model context. Shared API version bumped to **1.1.0** in both schemas and contract documentation for new routes/diagnostic fields.

Commands/results:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m backend.demo_setup
```

- **61 tests passed**, including all Phase 1 tests. Negative cases cover unknown sources, supplied-URL trust spoofing, authority/scheme/reference/date mismatches, missing review, unsupported partial documents, scans, malformed PDF bytes, altered evidence/values/scope/dates, bad targets/overlaps, immutable records and stale revisions.
- A forced event insert failure rolled back review, rules, decisions, revision and snapshot. Concurrent applies produced one winner and one 409, with one event. Restart resumed pending extraction. Cache reuse preserved document identity.
- New regressions were written/reproduced failing for missing effective-date evidence and inconsistent multi-query reads, then passed after fixes. Initial tests failed before the Phase 2 modules existed.
- Actual watcher test copied a new PDF, observed the measured SHA-256 and READY_TO_APPLY state, preserved FAIL until explicit apply, deduplicated a renamed copy, and verified shutdown health.
- Full synthetic PDF/API pair reproduced the Phase 1 gold result: **5 evaluated, 2 changed (1 improved, 1 review-required), 3 unchanged**. The mismatch PDF was quarantined. These are fixture outcomes, not benchmark accuracy scores.
- Schema import and all **39** contract-model JSON schemas passed. OpenAPI exposes actual v1.1.0 routes/models. `pip check`: no broken requirements.
- Real Uvicorn process on loopback: health, initial revision-0 workspace, actually running local watcher, Swagger and OpenAPI passed. The smoke server was stopped; start the server manually for further interaction.
- Three source PDFs rendered through bundled Poppler and all page PNGs visually inspected: legible, no clipped clauses. Poppler emitted missing display-font mapping warnings; rendered Helvetica text was intact. Runtime API boxes remain empty, so no exact highlighting claim is made.
- Non-blocking dependency note: Starlette 1.10.0 warns that its httpx TestClient adapter is deprecated. The adapter works and all tests passed; no warning was hidden.

**ASSUMED / scope:** only the declared notice-template grammar is parsed. Demo configuration trusts known generated PDF hashes and the operator-configured local folder; matching either is not cryptographic authenticity. Review names are local operator assertions, not authenticated identities. The demo evaluates the date 2026-10-30 in the Indian calendar; publication/acquisition chronology uses India's +05:30 date. Historical profiles are not editable through HTTP.

**UNTESTED / future:** arbitrary free-form notices, Hindi PDF rendering/OCR, Sarvam, authentication/remote deployment, frontend animations/review UI, exact coordinate highlights, a 20+ pair benchmark/baseline and full product offline replay. English PDFs and Hindi Phase 1 text fixtures are tested. No scorecard or live sponsor success is claimed.

## 3. Immediate first run — native Windows PowerShell

In the unpacked project root:

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install "pydantic>=2.9,<3"
.\.venv\Scripts\python.exe -m backend.schemas
```

**Expected:** prints `NiyamPulse schemas v1.1.0: import OK` and the beginning of a JSON Schema. It does **not** start a server. The Phase 2 server now exists; use `README.md` for dependency installation, synthetic setup and launch.

If PowerShell cannot find `py -3.12`, install/register Python 3.12 and rerun the version check. Do not switch to a different Python version silently.

## 4. Milestone plan (ordered by integration risk)

### M0 — Contract bootstrap (this delivery)

- [x] Document single coherent product story, trust boundaries and v1 scope.
- [x] Define typed rule, evidence, amendment, gate, profile, event, explanation and evaluation DTOs.
- [x] Freeze a planned `/api/v1` handshake and DTO naming.
- [x] Confirm on native Windows Python 3.12 and add an automated unit test command.

**Exit criterion:** clean import + schema build on Windows Python 3.12; team agrees that fields/endpoint names are stable.

### M1 — Pure decision engine and synthetic fixtures

- [x] Implement deterministic evaluators for five closed rule types.
- [x] Implement aggregate precedence and four statuses with explainable reason codes.
- [x] Implement effective intervals, targeted `ADD/REPLACE/REVOKE`, scope matching and conflict detection.
- [x] Build initial synthetic personas and at least three original/corrigendum fixtures (English and Hindi; UTF-8 text, not PDFs).
- [x] Unit-test FAIL→PASS, PASS→FAIL, UNKNOWN, CONFLICT, and unrelated amendment preservation.

**Exit criterion:** Python-only tests reproduce golden profile outcomes with no LLM or network dependency.

### M2 — Intake, immutable provenance, and SourceGate

- [x] Add SQLite schema, migration/bootstrap, document hash storage, extraction snapshots.
- [x] Add PDF intake API and local `watchdog` folder watcher with duplicate hash suppression.
- [x] Add quote/evidence verification and source-reference/authority/effective-date checks.
- [x] Require explicit reviewed approval; quarantine mismatches; commit atomically on revision match.
- [x] Implement preview/apply/events/timeline HTTP endpoints with OpenAPI response models.

**Exit criterion:** new controlled synthetic notice triggers a real preview; only reviewed supported amendments may change committed applicant results.

### M3 — High-impact frontend

- [ ] Build command center, version timeline, applicant grid, and status legend.
- [ ] Connect to real API state and event feed; poll and deduplicate event IDs.
- [ ] Animate only backend-derived `DecisionTransition` states.
- [ ] Build evidence inspector with PDF pages and graceful text-only fallback.
- [ ] Add source quarantine screen and visible disclaimer.

**Exit criterion:** an operator can see and explain a genuine deterministic decision shockwave without slides.

### M4 — Sarvam integration

- [ ] Verify API key and each actual endpoint with tiny test inputs; record versions/limits and cost.
- [ ] Add document OCR fallback for short scanned Hindi/Devanagari pages.
- [ ] Add `sarvam-105b` structured candidate extraction with explicit schema validation.
- [ ] Add a short Saaras Hindi/Hinglish question and Bulbul response.
- [ ] Validate Hindi facts and number/date preservation before audio; refuse unverifiable speech.
- [ ] Cache extraction/output by document hash and model version; label cache/replay accurately.

**Exit criterion:** real sponsor API calls are load-bearing on at least one end-to-end tested path.

### M5 — Evaluation, reliability and showcase

- [ ] Generate **20+** labeled synthetic document pairs, both English and Hindi/Devanagari.
- [ ] Save gold rule, supersession, date, source-gate, and applicant decision labels.
- [ ] Run end-to-end evaluation and preserve raw failures, numerator and denominator.
- [ ] Run honest single-LLM baseline on the same test set; if unavailable, hide baseline rather than fake it.
- [ ] Add offline replay and API/network-error indicators.
- [ ] Rehearse an uninterrupted 90-second product demo with one timed backup path.

**Exit criterion:** measured synthetic scorecard, reproducible run metadata, no invented metrics, documented failure cases.

## 5. Priority-ordered cuts (if schedule becomes constrained)

Protect the primary visual loop: **apply reviewed amendment → deterministic cohort impact → source proof**.

1. Cut nationwide/remote crawlers; keep genuine local-folder monitoring.
2. Cut arbitrary language choices; support Hindi text and a single tested Hindi voice route.
3. Cut full two-clock historical exploration; retain a simple effective-date timeline.
4. Cut exact text-box highlighting on unreliable OCR pages; retain page + literal quote proof.
5. Cut live baseline comparison UI; retain documented offline evaluation scores if actually measured.
6. Cut advanced visual effects; keep clear animated status transitions.
7. Cut extra sponsor integrations and multi-agent orchestration.

Do **not** cut the actual rule evaluator, provenance gate, review approval, real impact computation, or source evidence. If these cannot work, do not label a scripted animation as a functional product.

## 6. Open questions and fastest tests

| Question | Current answer | Fastest resolution |
|---|---|---|
| Does hackathon permit writing/submitting product code before event? | **User-supplied brief says yes; public rules not independently confirmed.** | Ask organizer for written clarification and preserve timestamped repo history. |
| Do credited Sarvam endpoints work in this account? | **Untested** | Make one tiny structured generation call, one 1-page Vision request, one <30s Saaras request, one short Bulbul output. |
| Can OCR yield exact quote positions for a Hindi PDF? | **Untested** | Use a 1-page Devanagari sample; compare OCR text and bounding boxes against original page rendering. |
| Do Pydantic models work on native Windows Python 3.12? | **Verified:** Python 3.12.10 / Pydantic 2.14.2 | Current v1.1.0 schema import, all 39 model JSON schemas and 61 tests passed. |
| How to prove local watcher truly detects new notices? | **Verified in native test and real-server health** | Stable copied PDF was detected with matching SHA-256 and no automatic apply; UI demonstration remains Phase 3. |
| Does the baseline do worse than the structured engine? | **Unknown until evaluated** | Run both on the same labeled synthetic cases; never predict a score. |

## 7. Risks / limitations to keep visible

- The system supports **five narrow rule types** only. It cannot interpret arbitrary legal/administrative exceptions safely.
- A matching authority name, reference, or configured URL is not definitive proof a document is authentic.
- The application is **decision support**, not official eligibility approval or legal advice.
- LLM/OCR extraction can be wrong. Exact source quoting, typed validation, review gates, and abstentions reduce risk but do not eliminate it.
- Synthetic benchmark scores are evidence for the **synthetic distribution tested**, not real-world accuracy.
- Applicant information must be minimized and handled with appropriate consent and controls in any non-demo deployment.

## 8. Work log

| Date | Work | Tests / evidence | Next step |
|---|---|---|---|
| 2026-10-30 | Initial four-file contract scaffold | Pydantic import and JSON Schema generation in Python 3.13.5/Linux; Windows 3.12 pending | M0 Windows run, then M1 pure rules + gold fixtures |
| 2026-10-30 | Verified M0; implemented M1 evaluator, uncommitted amendment planner, PREVIEW impact, strict synthetic text parser, 3 pairs/13 profiles, tests and local tooling | Native Windows Python 3.12.10 / Pydantic 2.14.2; `python -m backend.schemas`; `python -m unittest discover -s backend/tests -v`: 37 passed; `python -m backend.synthetic_demo`: 3 pairs matched gold; maximum-date regression reproduced then fixed | M2 PDF intake, immutable extraction/source gate, review and transactional API |
| 2026-10-30 | Implemented M2 PDF/SQLite/source-gate/review/apply API, actual local watcher, v1.1.0 contracts, synthetic PDFs, walkthrough and model handoff | Native Windows Python 3.12.10: 61 tests passed; 39 JSON schemas; pip check; real Uvicorn HTTP smoke; Poppler visual inspection; rollback/concurrency/read-snapshot regressions verified | M3 real API-driven frontend |

**Next owner task:** M3 frontend — generate TypeScript from actual OpenAPI 1.1.0, connect review/source inspection and four-status profiles to real API data, poll/deduplicate events and animate actual transitions. No Sarvam credentials are needed yet. Manual backend review steps are in `README.md`.
