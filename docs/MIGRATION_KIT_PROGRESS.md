# PROGRESS.md — NiyamPulse direction change tracker

**As-of 2026-10-30.** Scope: broad India exam tracking for school students and engineering aspirants; notifications by subscription; source monitoring and personal-impact checking. Target **Windows / Python 3.12**. **This package is a migration specification and shared-model starter; it is not a deployed product.**

Legend: ✅ DONE in this delivered kit · 🟡 PARTIAL / old work unknown · ⬜ NOT STARTED in this kit · 🧱 BLOCKED by validation/access.

## A. Scope change (decision locked)

- ✅ **User experience**: subscribe once to multiple exam cycles; new official updates should be fetched by NiyamPulse, not uploaded manually by end users.
- ✅ **Audience**: JEE Main, NEET UG, NDA/NA; GATE, UPSC ESE, SSC JE; expandable to JEE Advanced, CUET UG, BITSAT, VITEEE, RRB JE, ISRO/DRDO/PSU opportunities.
- ✅ **Admin**: source monitoring health, review queue, publication, matching, sent/read/failed notifications and aggregates from DB.
- ✅ **Logic**: distinguish informational notices from validated changes to five supported deterministic rules.
- ✅ **Privacy**: subscriptions work without DOB or other personal profile data. Personalization is opt-in and does not verify real-world applications.
- ✅ **Sponsor**: Sarvam OCR/extraction/Indic explanation and optional STT/TTS remain load-bearing parts, with strict evidence and validation.
- ✅ **Manual documents**: remain operator-only fallback/testing path, not core subscriber workflow.

## B. Delivered migration artifacts

| File | Kit state | Notes |
|---|---|---|
| `AGENTS.md` | ✅ DONE | Agent policies, scope, architecture, Windows commands |
| `SHARED_CONTRACTS.md` | ✅ DONE | Planned `/api/v2` endpoints and matching/delivery rules |
| `backend/schemas.py` | ✅ DONE | New v2 strict Pydantic DTOs with old rule union reused |
| `backend/legacy_schemas_v1.py` | ✅ DONE | Unmodified prior v1 `schemas.py` backup |
| `config/exam_catalog.json` | ✅ DONE | Cross-audience catalog, **not a coverage guarantee** |
| `config/source_registry.json` | ✅ DONE | Official listing URLs; adapters **disabled** until tested |
| `docs/EXAM_SOURCES.md` | ✅ DONE | Exam coverage, official URL checks, source rollout |
| `CODEX_MIGRATION_PROMPT.md` | ✅ DONE | Exact prompt to give existing Codex project |
| `tests/test_schema_contracts.py` | ✅ DONE | Local contract-level smoke tests, not app tests |
| `MIGRATION_README.md` | ✅ DONE | Safe overlay + Windows commands |

## C. What Codex may have already implemented

🟡 **UNKNOWN**: some v1 code was reportedly written in the user's repository. The repository was not supplied, so this kit CANNOT certify, replace, or enumerate that work. **Codex MUST inspect git status / tree / imports / endpoints / existing tests and present an impact map before migrating.** Preserve working old code, keep `legacy_schemas_v1.py`, and do not overwrite customized files without merge.

## D. Local checks for this delivered kit

- ✅ `python -m backend.schemas` ran on **Python 3.13.5 / Linux** with **Pydantic 2.13.5** and passed schema JSON generation.
- ✅ JSON catalog/registry validates against `ExamCatalogEntry`, `ExamCycle`, and `OfficialSource` models in the build container (when packaging completes).
- ✅ `python -m pytest -q`: **8 passed in 0.14s** on Python 3.13.5 / Linux, Pydantic 2.13.5. These are contract tests, not functional monitor/application tests.
- ⬜ **Windows Python 3.12** tests have **not** run in this environment; user/Codex must run on native Windows.
- ⬜ No live crawling test, Sarvam account call, app backend, authentication, notification delivery, or deployed metrics has been performed by this kit.

## E. Prioritized next tasks for Codex (do not mark done without execution)

### M0 — Audit & migration merge
- [ ] Print repository tree, git status, existing routes/models/services/tests and reused v1 modules.
- [ ] Determine compatibility layer for existing imports; integrate new files safely.
- [ ] Test Windows Python 3.12 imports, schemas and existing tests.
- [ ] Commit migration-only changes so rollback is possible.

### M1 — Multi-exam subscriptions and in-app inbox
- [ ] SQLite models + migration for exam catalog/cycles, users, subscriptions, updates and notifications.
- [ ] Backend `/api/v2/catalog`, `/api/v2/me/subscriptions`, `/api/v2/me/notifications`.
- [ ] Two frontend views: user exam picker + notification feed; admin operations dashboard scaffold.
- [ ] Ownership/auth or clearly labeled **local single-user demo mode** (no false public security claim).

### M2 — Automated source monitoring (real)
- [ ] Implement 2 official-source adapters, across different publishers, with real test fixtures.
- [ ] Observe listing links, canonical URLs, hashes, timestamps, dedup, last_success, last_error, status.
- [ ] Scheduler capable of running without the frontend; safe intervals, official allowlists, no CAPTCHA bypass.
- [ ] Test newly published item detection, re-poll idempotency, parse changes, timeouts.

### M3 — Notice review -> targeting -> notification delivery
- [ ] Implement intake, source gate, five-rule extraction policy, evidence validator + review approval.
- [ ] Topic/cycle mapping, optional deterministic applicant impact, **no LLM-per-subscriber**.
- [ ] Atomic publication/outbox, persisted in-app notifications and marking read, audit history.
- [ ] Admin counters derived from DB; target only relevant subscribers.

### M4 — Sarvam + accessibility + proof
- [ ] Test actual credential endpoints; enforce limits, cache and log cost/latency.
- [ ] Use structured 105B outputs plus Vision for scanned Indic PDFs, show source quote/page.
- [ ] Hindi explanation; optional tested Saaras mic input and Bulbul output with numeric/date guards.

### M5 — Tests, evaluation and honest demo
- [ ] Synthetic multilingual notice corpus, known exam-routing and relevance labels.
- [ ] Metrics: notice discovery, dedup, correct cycle routing, review gate, subscriber match, personalized decision flips, delivery success; measured counts only.
- [ ] End-to-end run: subscribe → new official listing detected → review → notify → user inbox → admin counts.
- [ ] Offline replay from honest recorded artifacts; no fake live indicators.

## F. Demo success definition

An operator sees a new notice from a **genuinely monitored official listing** OR a clearly labeled cached fixture, approves it, and the app automatically targets test subscribers tracking that exact exam cycle. A school-student user and an engineering user each receive only relevant in-app notices. The admin dashboard displays counts based on DB records. If one tested notice changes a supported rule and required facts exist, deterministic status changes and evidence are displayed; otherwise use informational notification without eligibility claims.
