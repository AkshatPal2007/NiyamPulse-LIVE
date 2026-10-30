# PROGRESS — NiyamPulse v2 migration

**Updated: 31 October 2026 (IST). Native Windows / Python 3.12.10.**

The current product is a multi-exam subscription and notification platform, not
an upload-first scholarship dashboard. The first v2 informational vertical slice
is implemented. V1 code, schema 1.1.0, APIs, tests, fixtures and documentation are
preserved; earlier progress is archived in `docs/legacy-v1/PROGRESS.md`.

## M0 — Audit and safe contract merge: DONE

- Clean starting checkout: `70ada56`; backend only, no existing frontend.
- Audited reusable evaluator, amendment planner, PDF/evidence handling, SQLite
  transactions and FastAPI routes. See `docs/MIGRATION_AUDIT.md`.
- Preserved this repository's newer schema 1.1.0 byte-for-byte as
  `backend/legacy_schemas_v1.py`; did not replace it with the kit's older copy.
- V1 modules import their explicit legacy DTOs. Remaining old symbol imports
  forward to legacy without payload conversion. `/api/v1` stays operational.
- Integrated v2 contracts, catalog, disabled source registry and supplied tests.
- Verified native baseline: **61 existing tests passed**, then **8 supplied v2
  contract tests passed**. `python -m backend.schemas`: v2 imports/schemas passed.

## M1 — Catalog, owned subscriptions and inbox: DONE for local demo

- Additive v2 SQLite tables; no v1 records or working modules deleted.
- Public searchable audience catalog; server-owned cycle/topic subscriptions,
  update/pause/unsubscribe, self-reported application status.
- Expiring opaque local demo sessions. `/me` derives ownership from the session;
  `/admin` checks operator role. Three seeded pseudonymous identities are marked
  SYNTHETIC DEMO. This is not production authentication.
- Optional profile fields require explicit personalization opt-in; removal and
  account deletion revoke sessions and delete owned subscriptions/inbox records.
- Private signed-cursor inbox, newest-first pagination, idempotent marking read.
- Responsive React/TypeScript/Vite/Tailwind UI with distinct learner/operator
  experiences; types generated from actual FastAPI OpenAPI.
- Browser walkthrough: school learner followed JEE, engineering learner followed
  GATE; a reviewed synthetic JEE update reached only the school learner. Opening
  it persisted READ. The engineering inbox stayed empty.

## M2 — Two real source adapters: DONE within declared scope

- Real direct HTTP checks performed on **NTA JEE Main** and **UPSC active exams**,
  different publishers. Both listings returned HTTP 200. Actual downloads were
  extracted and one mapped notice per source persisted locally.
- Native command `python -m backend.monitor --check nta-jee-main --discover --enable`:
  1 recognized link, 1 created notice, no errors. JEE Main 2027 Session 1.
- Native command `python -m backend.monitor --check upsc-active --discover --enable`:
  5 recognized links, 1 created notice, 4 explicitly unmapped older cycle items,
  no errors. UPSC ESE 2027. No routing of 2026 NDA/ESE items to 2027 subscribers.
- Both source adapters enabled in the **local runtime database** only after those
  successful checks. Checked-in registry defaults remain disabled for new setups.
- Exact HTTPS hosts, public DNS/address checks, bounded downloads, validated
  redirects, robots checks, hourly scheduling, error reporting and cooldowns.
- NTA's robots file allows the public listing. UPSC's robots URL redirects to
  its homepage with no directives; the exact nonstandard result is recorded.
  This is not proof of permission, authenticity or complete site coverage.
- Source worker is independent of the frontend and can run as its own Windows
  process. Runtime health/heartbeat is observed, not fabricated.
- Actual HTML/robots captures and hashes are in `tests/fixtures/official/`.
- Regression reproduced then fixed: footer visitor-counter changes must not create
  another notice. Meaningful extracted-content hashes drive dedup; immutable raw
  captures retain actual byte hashes.
- Scope: NTA listing/PDF notices and UPSC active-exam detail pages. Deep attachment
  crawling, pagination across archive years and the other publisher adapters remain
  future increments. No nationwide/all-exam coverage claim.

## M3 — Review, informational matching and delivery: DONE; rule bridge PARTIAL

- Immutable raw source captures and extraction snapshots; evidence binds source
  byte hash, extraction version/ID, page and exact offsets.
- Live publication rechecks listing lineage, exact cycle mapping, stored hashes
  and frozen quotes. Rule-like notices requiring validation cannot bypass the
  deterministic bridge through informational approval.
- Operator identity checked against the authenticated session; expected notice
  revision and deterministic request hash provide stale-write/idempotency checks.
- Review, immutable update, deterministic cycle/topic matches and in-app delivery
  persist in one transaction. Unique `(update_id,user_id)` prevents duplicate alerts.
- Generic updates use GENERAL_UPDATE with no before/after decision pair. There is
  no per-subscriber LLM call and no invented PASS/FAIL or application confirmation.
- Forced delivery-write failure was tested: review/update/matches/alerts rolled
  back together. Altered immutable-text binding was reproduced failing, then fixed.
- V1's five-rule evaluator remains authoritative and fully tested. Publishing v2
  personalized rule changes is intentionally held until its evidence/review bridge
  and opted-in profile mapping are completed.
- Admin counters and per-cycle charts derive from persisted database records.

## M4 — Sarvam and accessibility: PARTIAL; text/OCR integration implemented

**DONE / VERIFIED:**

- User configured the key locally and explicitly authorized a **₹50 total test
  budget**. No key was printed, copied to frontend, or committed. `.env` is ignored.
- Additive migration 003: immutable model cache, request/reservation ledger, saved
  OCR jobs and notice-analysis projection. Existing v1/v2 data remains preserved.
- Real `sarvam-105b` requests authenticated successfully. Fixed bounded output,
  non-thinking mode, strict JSON schema, source/prompt/version keyed cache,
  timeouts, server-side role/revision checks and persistent integer-paise cap.
- Literal/date/topic/cycle guards reject invented or unsupported candidates.
  Whitespace-only folded quotes resolve only to one exact immutable source span.
  Rejected candidates cannot publish, including through direct API calls.
- Actual **UPSC ESE 2027 captured detail page** produced a VALIDATED candidate.
  English summaries are extractive. Controlled Hindi labels copy verified source
  values and retain original passages, without guessing numeric date conventions.
- Actual **NTA three-page PDF** had badly garbled embedded text. The first AI
  proposals failed the quote guard. Sarvam Vision/Document AI completed **3/3 pages**.
  Its observed `digitise`/page-block response differs from SDK 0.1.41's union; a
  regression-tested REST result reader handles it. The existing job was resumed,
  never resubmitted just to fix client parsing.
- Immutable raw PDF, prior embedded extraction, raw OCR cache and a versioned
  HTML-table-to-text extraction are retained. No page boxes are claimed verified.
- NTA fact proposals **still fail exact evidence checks** after OCR and remain
  GUARD_REJECTED/held. This is not reported as extraction success or publication.
- Blank/scanned PDFs are now retained as NEEDS_EXTRACTION instead of being lost;
  they cannot publish or enable an adapter until usable text exists.
- Local budget ledger: **7 admitted operations (6 chat requests + 1 OCR job),
  ₹35 reserved of ₹50**, 11,605 provider-reported prompt tokens and 3,647 completion
  tokens. GET status/result reads and cache replay create no additional reservation.
  Reservations are conservative local allowances, **not measured provider bills**.
- Admin UI shows cache/provenance/coverage, guarded Hindi overview, budget state,
  OCR recovery and publication hold. Language preference selects frozen reviewed
  summaries; no per-subscriber model calls.
- Local synthetic tests verify Hindi fan-out, tampered-summary rejection, incomplete
  outputs, identity/role/stale writes, quota/budget failures, OCR page coverage,
  empty-text retention and source-byte preservation.

**PARTIAL / manual gate:** the genuine UPSC candidate is ready for human source
review, not auto-approved. Genuine NTA stays held. Existing synthetic publications
and user-created subscriptions were preserved; no genuine notice was published.

**NOT STARTED:** free-form Hindi generation/translation evaluation, voice input,
TTS, production login and the v2 personalized-rule publication bridge. The old
Python evaluator remains authoritative; informational alerts invent no decisions.

## M5 — Verification and demo: DONE for the first informational slice

**VERIFIED** in this checkout:

- Initial migration suite: **82 passed**. Latest Sarvam/OCR combined native suite:
  **101 passed**, **38 unittest subtests passed**, one non-failing dependency
  deprecation warning; 32.21 seconds. Production UI build, schema smoke and
  `pip check` passed after the integration.
- Reproduced and fixed test-package collection collision with importlib mode.
- Reproduced and fixed a source-enable dry-run bypass: enabling now requires
  real mapped document discovery/extraction; CLI rejects incomplete arguments.
- Production UI build passed: TypeScript and Vite, with generated API types.
- Schema smoke and `pip check` passed. The preserved v1 schema matches commit
  `70ada56` byte-for-byte. `git diff --check` passed.
- Production FastAPI `/`, `/api/v1/health`, `/api/v2/status`, `/api/v2/catalog`
  returned HTTP 200. Browser loaded built UI without console errors.
- Genuine student/admin screenshots saved under `output/screenshots/`.
- Browser flow verified subscriptions, review, correct recipient exclusion,
  delivered alert, literal evidence and read state.
- Responsive DOM bounds checked at desktop width (1425 CSS pixels): no horizontal
  overflow, three-column grid. Mobile visual checks performed in the in-app browser.
- Existing non-failing Starlette httpx TestClient deprecation remains visible.
- No accuracy scorecard, benchmark baseline or full Sarvam/voice/rule pipeline exists.

Exact commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m backend.monitor --check nta-jee-main --discover --enable
.\.venv\Scripts\python.exe -m backend.monitor --check upsc-active --discover --enable
```

## Remaining / next smallest increments

1. Human source review of the genuine UPSC informational notice; NTA remains held
   until its candidate evidence passes. Then verify a real-source alert with a
   synthetic subscribed learner.
2. V2 validated personal-rule amendment bridge into the preserved evaluator.
3. More source adapters, attachment-level monitoring and exact cycle fixtures.
4. Real account authentication and public-deployment privacy/consent controls.
5. Multilingual evaluation corpus, measured metrics and replay from recorded inputs.

## Design assumptions and practical limits

**ASSUMED:** this is a loopback-only prototype with synthetic local identities.
In-app DELIVERED means a persisted private inbox row. One source worker is run
at a time; coverage is bounded to the implemented listing/detail adapters.

**UNTESTED / not implemented:** free-form Hindi generation/audio, production
authentication, all-exam coverage, v2 personalized rule-change publication and
benchmark accuracy. No success or scorecard is claimed for these.

All migration changes remain local for review; no Git push or public deployment
was performed. Only agent-owned verification servers are stopped after QA. A pre-existing user
server on port 8000 was left untouched. Restart it with `--env-file .env` to load
the new integration. The temporary verification server uses port 8001 without a
second source worker.


## Current human handoff gate

Stop/restart your existing local API with `--env-file .env`. The synthetic
Engineering learner is already subscribed to UPSC ESE 2027 with Hindi preference,
prepared through the actual UI. No real applicant data was added. Switch to
Platform operator, open the genuine Engineering Services (Preliminary) Examination,
2027 notice, open its original source, compare exact dates/cycle, enter a review
reason and approve only if satisfied. Return to that learner's inbox and open the
new alert. NTA must stay held/quarantined; no bypass of its rejected evidence.
Human review is required by AGENTS.md invariant 3. This is the next manual action;
no real applicant personal data or official application submission is needed.
