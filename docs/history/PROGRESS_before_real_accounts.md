# PROGRESS — NiyamPulse v2 migration

**Updated: 31 October 2026 (IST). Native Windows / Python 3.12.10.**

The current product is a multi-exam subscription and notification platform, not
an upload-first scholarship dashboard. The first v2 informational vertical slice
is implemented. V1 code, schema 1.1.0, APIs, tests, fixtures and documentation are
preserved; earlier progress is archived in `docs/legacy-v1/PROGRESS.md`.

> **Latest milestone (31 October 2026):** future-plan phases 1–3 are implemented;
> genuine phase-2 human acceptance is confirmed in persisted data. **173 tests +
> 38 subtests pass**, and the production build passes. The closed-rule bridge is
> stabilized; NTA's informational hold is fixed; three real source adapters and
> a durable, budget-aware processing queue are exercised. User-approved UPSC ESE
> produced exactly one real-source update and a READ alert for the synthetic
> Engineering learner. The prior ₹50 local cap is fully reserved; further paid
> calls are paused and the 500-credit floor is enforced. See
> [phase report](PHASES_1_3_REPORT.md) and [next phases](../FUTURE_PLAN.md).

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
- NTA OCR quote alignment was resolved: LLM candidate added separator colons to table
  row headers (e.g. `Date of Examination: ...` vs OCR page text `Date of Examination\n...`).
  `resolve_literal_spans` now permits only closed announcement label/newline
  alignment to bind the exact original page string; other punctuation stays strict. NTA notice reprocessed from cache as VALIDATED with zero extra token spend.

**Current acceptance:** both NTA and UPSC extractions are VALIDATED under the
narrower, versioned source guard. NTA's informational false positive is fixed.
The user reviewed genuine UPSC, received its matching Engineering alert and
marked it read. Closed-rule publication is implemented/tested as described below;
unsupported exam conditions remain held.

**NOT STARTED:** free-form Hindi generation/translation evaluation, voice input,
TTS and production login. Full personal-profile/impact UI remains phase 4.
The old Python evaluator remains authoritative; informational alerts invent no decisions.

## M5 — Rule bridge stabilization: DONE for the closed supported subset

- Replaced unsafe free-form guesses with explicit literal source context and the
  existing five-type EN/HI clause grammar; unsupported batches remain held.
- Independently recompute values/scope/targets/evidence at publication. Explicit
  change/rule attestations replace self-trusting model proposals.
- Migration 005 stores full immutable rule history and optimistic per-cycle
  revisions. ADD/REPLACE/REVOKE decisions and hashes survive reload unchanged.
- Publication is atomic and uses the India calendar. Stale analysis, tampered
  values/flags, missing proofs and invalid chronology fail closed with no fanout.
- Public schemas/contracts/types updated together. Legacy engine is preserved.
- Full natural-language exam eligibility and complete profile UI remain future work.
  Details and genuine test evidence: docs/PHASES_1_3_REPORT.md.

## M6 — Future-plan phases 2–3: DONE within declared scope

- NTA and UPSC cached facts revalidated with exact immutable source anchors;
  source mentions do not silently become operative rules.
- Human-confirmed UPSC acceptance: one approved update, one matching Engineering
  learner alert, READ, English per the user's current preference. User confirmed
  the working flow; additional subscriptions/preferences remain untouched.
- Added real NEET 2026 post-exam notices, ten observed mapped documents, fixtures,
  bounded rotating polls and a real 62-page UPSC attachment with verified ancestry.
- Durable extraction queue, lease/restart safety, bounded retries, per-source
  failure isolation, cache reuse, credit-floor protection and truthful admin UI.
- Three new paid operations were admitted within the existing cap. One failed
  the evidence guard; real Vision recovery and guarded 105B facts succeeded for
  another notice, which remains held for unsupported legal-rule content.
- Current cap: 5000/5000 paise conservatively reserved across ten operations.
  500-credit minimum and expiring manual balance snapshot required for admission.
- Native final suite: 173 tests + 38 subtests; UI build/schema/pip checks pass.


## Remaining / next smallest increments

1. Phase 4: complete opt-in personal-profile and impact UI for the supported rule subset.
2. Phase 5: multilingual/edge-case corpus, measured metrics and reproducible replay.
3. Phase 6: production identity, privacy/consent and operational hardening.
4. Phase 7: rehearse the real-source demo and recovery checklist.
5. Keep unsupported notices held and paid processing paused at the current cap.
   Further source coverage or spending requires the relevant evidence/budget decision.

## Design assumptions and practical limits

**ASSUMED:** this is a loopback-only prototype with synthetic local identities.
In-app DELIVERED means a persisted private inbox row. One source worker is run
at a time; coverage is bounded to the implemented listing/detail adapters.

**UNTESTED / not implemented:** free-form Hindi generation/audio, production
authentication, all-exam coverage, arbitrary personal exam eligibility, full
profile/impact UI and benchmark accuracy. Closed-set publication is tested. No success or scorecard is claimed for these.

All migration changes remain local for review; no Git push or public deployment
was performed. Only agent-owned verification servers are stopped after QA. A pre-existing user
server on port 8000 was left untouched. Restart it with `--env-file .env` to load
the new integration. The temporary verification server uses port 8001 without a
second source worker.


## Current human handoff gate — completed

The user reviewed and approved the real UPSC ESE metadata notice, inspected the
matching Engineering inbox alert and marked it read. Runtime records confirm
APPROVED revision 6, one real-source update, and one READ English notification.
No further source approval is required for this milestone. Paid extraction stays
paused at the cap; do not interpret this as a reason to increase spending.
Restart the user-owned backend on its next reload to load the last queue bookkeeping
and excerpt-offset fixes; the agent did not stop port 8000. See the phase report.


## Full-project review and cleanup — 31 October 2026

- Reviewed current source, tests, contracts/configuration, UI, migrations and a
  read-only runtime database snapshot; preserved newer uncommitted bridge edits.
- Fresh native run: **132 tests passed, 38 subtests passed** in 28.71 seconds;
  frontend production build, schema smoke and pip check passed.
- Separate synthetic audit probes reproduced marks-exemption inversion, passport
  mapped to Aadhaar, inferred dates, and a REPLACE plan that evaluates PASS but
  reloads from SQLite as CONFLICT. These expose missing negative/roundtrip coverage;
  a passing current suite is not acceptance of the personal-rule feature.
- Runtime migration 004 is not yet applied to the inspected real data directory.
- Prior committed slice is at `1a9b713`; this audit did not commit or push changes.
- Removed **13 ignored generated targets**, **1,320,936 bytes** reclaimed, no skips.
  Duplicate HTTP probes were hash/metadata checked against tracked fixtures first.
  Kept source, credentials, runtime data/model caches, dependencies, built UI,
  verified fixtures/screenshots, Git history and all active code edits.
- No paid API calls, source approvals, real notifications or server shutdowns
  were performed by this review. See docs/PROJECT_REVIEW.md and docs/FUTURE_PLAN.md.
