# AGENTS.md — NiyamPulse v2 (source of truth for Codex)

**Updated 2026-10-30. Target: native Windows, Python 3.12.** Read this file, `SHARED_CONTRACTS.md`, `PROGRESS.md`, `docs/EXAM_SOURCES.md`, and `CODEX_MIGRATION_PROMPT.md` before editing code. This is a **migration of an existing repository**, not permission to delete existing work.

## 1. Mission / product definition

**NiyamPulse is a subscription-based, multilingual exam-update intelligence platform for Indian school students and engineering aspirants.** A person chooses exams/cycles (e.g., JEE Main 2027, NEET UG 2027, NDA I 2027, GATE 2027, UPSC ESE 2027, SSC JE 2026, SSC CGL 2026). The system periodically checks configured official announcement pages, identifies new notices, verifies source lineage, extracts evidence-linked changes, matches subscribed users, and produces in-app notifications. The operator dashboard shows genuine source health, notice review, subscriber matching and delivery metrics. **Users should not have to upload new PDFs** to receive updates from supported live sources.

Manual upload remains **admin-only fallback / development test facility**. This is NOT a PDF chatbot. Multi-exam catalog and subscription design are core, not SSC CGL-specific.

### Non-negotiable invariants

1. **LLM extracts/explains; deterministic Python code decides.** AI may generate proposed structured data, never official eligibility decisions, personal targeting, trust approval, or final numbers.
2. Official-source **hostname matching is not cryptographic authenticity verification**. Record exact source URL, observed listing link, content hash, downloaded timestamp, publisher reference and validation steps. Never label a source officially certified.
3. **No silent update propagation**: MVP routes notices through SourceGate and human admin review. Only approved supported updates create notifications. Quarantine unknown authority/reference conflicts or unsupported/ambiguous rules; informational notices may be approved and broadcast by subscription topic without eligibility claims.
4. **Four deterministic decision states** are `PASS`, `FAIL`, `UNKNOWN`, `CONFLICT`; only use when supported rule evaluation really ran. Exam news that does not modify an evaluable rule is **GENERAL_UPDATE**, not `PASS`.
5. Supported personal-rule types are *only* `minimum_marks`, `maximum_income_inr`, `application_deadline`, `age_bounds`, `required_documents`. Exams have more complex real eligibility; outside this closed set must abstain / request review. Age relaxations, quotas, qualifying marks, domicile, academic branch, subject combination, physical/medical standards are NOT silently covered.
6. **No fabricated users, affected counts, notifications, delivery rates, benchmark scores or API calls.** Seed demo data only with conspicuous `SYNTHETIC_DEMO` labels. Real dashboard counters derive from database queries.
7. **Never claim users have applied through an official portal.** `APPLIED_SELF_REPORTED` means exactly that. We never impersonate exam boards or submit official applications.
8. Include visible disclaimer: *"Decision support only; not official eligibility or application confirmation."* Always link to official notice.
9. Protect minors and sensitive candidate data: profile fields optional; collect no DOB, marks or income without explicit opt-in, implement account ownership checks and deletion. Reassess applicable privacy/child-consent requirements before public deployment. Use generated pseudonymous identities in demos.
10. Offline replay loads **cached recorded inputs**, labeled as such. It runs the actual relevance/decision/notification logic. No pretend background watcher or prerecorded fake network success.
11. **Native Windows 3.12**: use `pathlib`, PowerShell-compatible commands, SQLite local development, `.env`, no Bash-only runtime requirement. Never require Docker, Redis, Celery, Kafka or WSL for local MVP.
12. Do not hardcode yearly GATE organizer pages as global forever URLs: source adapters must be versioned/configurable per exam cycle.

## 2. Build the correct product in this order

**P0 migration & contracts** — Audit existing repo, retain working components, keep schema-v1 compatibility; introduce v2 exam catalog, user subscription, source watcher, notice update, recipient match and notification DTOs. Agree on `/api/v2` HTTP handshake. Do not rewrite v1's deterministic engine purely for naming reasons.

**P1 real subscription slice** — Display multi-exam catalog; user can subscribe to multiple active exam cycles (no personal data required), inspect own notifications; admin sees counts from database. Use seeded synthetic notices with explicit badges until fetch works.

**P2 genuine source monitoring** — Implement at least **two source adapters with different publishers**: ideally NTA JEE Main (or NEET UG) + UPSC NDA/ESE or the GATE 2027 official notifications page. The source monitor should run as a background process, configured per source, with last-success, last-error and newly discovered link counts. Test HTML changes and rate limits. Only enable a source after an adapter has proven extraction on an actual page.

**P3 notice/relevance pipeline** — Immutable raw HTML/PDF capture, dedup by source/URL/content hash, source gate, review queue, classification, one update per reviewed notice, fan-out by exam-cycle + topic, in-app notification persisted to DB with dedup `(update_id, user_id)`. Generic exam notices do NOT need the eligibility rule engine. Optional personalized decision changes use existing pure Python engine when all required facts/rules are known.

**P4 Sarvam integrations** — Integrate Vision (when needed), 105B structured classification/extraction and evidence-linked Hindi explanation, optional Saaras/Bulbul. API calls only with actual key, timeouts, budget logging, response validation, and cache; no imaginary success.

**P5 admin + tests + demo** — Sources health, pending reviews, recent notices, delivered/read, per-update matched subscribers and computed decision flips, source references, replay mode, real evaluation (synthetic labeled data). A 90-second operator demo showcases discovery -> review -> fanout -> per-user notification and admin counters.

## 3. Architecture & ownership

- `backend/schemas.py`: v2 **data transfer objects only**, strict Pydantic v2.
- `backend/legacy_schemas_v1.py`: frozen old contracts used by earlier code, including five rule union members, decision/evidence types. Gradual imports permitted. Do not remove until references are migrated and all tests pass.
- `backend/api/`: thin FastAPI routes (to be built), auth/ownership and typed responses.
- `backend/services/source_monitor/`: source-specific listing adapters, scheduler, HTTP fetcher, dedup, provenance. Poll only allowlisted official endpoints; disable untested adapters.
- `backend/services/notices/`: intake, classification, evidence validation, source gate, review + atomic publication.
- `backend/services/rules/`: pure deterministic rule engine and version resolver; port existing logic if present.
- `backend/services/relevance/`: match cycles/topics first; only then optional deterministic profile impact.
- `backend/services/notifications/`: persistent in-app delivery, idempotency, mark read, audit trail.
- `backend/services/sarvam/`: API wrapper, retries, cache, structured result validation.
- `backend/storage/`: SQLite dev persistence, migrations, source snapshots, users, profiles, exams/cycles, subscriptions, notices, approvals, updates, matches, notification events.
- `frontend/`: React + Vite + TypeScript and simple Tailwind; student subscriptions + notification feed and separate admin operations UI. Existing UI reuse is encouraged.
- `config/exam_catalog.json`, `config/source_registry.json`: declarative **initial catalog**, verified link candidates, disabled crawlers by default.
- `tests/`: Python contract, pure business logic, adapter fixtures, matching and quarantine tests. Use isolated synthetic users.

## 4. Minimal persistence / security

Implement DB uniqueness constraints: `(user_id, cycle_id)` subscriptions, `(source_id, canonical_url, content_hash)` observed notices, `(update_id, user_id)` in-app notifications, and stable idempotency keys for review/dispatch. Make dispatch transactional using an outbox or equivalent DB transaction. Compute dashboard counts from persisted records, not UI state. No API key in git. Admin operations require admin authorization and optimistic revision checks; users can access ONLY their own profiles and notifications. Sanitize HTML, validate download content type/size, reject redirects to non-allowlisted hosts, block local/private network destinations (SSRF).

## 5. Local Windows commands

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-contracts.txt
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pytest -q
```

If existing repo has its own dependency manager, adapt appropriately without destroying lockfiles. Use `node`/`npm` only if the actual frontend is React. Ask before adding cloud costs or authentication providers.

## 6. Definition of done / Codex reporting

At each step update `PROGRESS.md` using **DONE / PARTIAL / NOT STARTED / BLOCKED** and cite executed commands and observed results. Report actual changed files, endpoint paths and smoke test output. Do not mark a remote page source "live" until an actual poll detects an official listing item. Keep this architecture and `SHARED_CONTRACTS.md` in sync with schema changes.

## Existing-repository migration notes

- The preserved v1 schema is this repository's tested **1.1.0**, not the kit's older copy. V1 services import it explicitly.
- V1 APIs and all earlier tests remain operational. Archived v1 documentation is under `docs/legacy-v1/`.
- `backend/storage.py` is an existing module; do not replace it with a directory. V2 storage is added separately.
- Native local development is the deployment scope for this migration slice. Do not register a hosted Site or send data to a cloud deployment.
