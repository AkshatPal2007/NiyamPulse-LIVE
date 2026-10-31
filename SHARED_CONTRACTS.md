# SHARED_CONTRACTS.md — NiyamPulse v2 Frontend ↔ Backend Handshake

**Contract version:** `2.0.0` · **Target:** Python 3.12, Pydantic v2, FastAPI + React/TypeScript. The first informational vertical slice is **implemented locally**; remaining integrations are listed below. Models in `backend/schemas.py` are canonical for field names and enums. Keep old `/api/v1` stable during migration; add `/api/v2` instead of silently changing existing payloads.

## 1. The new user journey

1. User sees an exam catalog organized by `SCHOOL` / `ENGINEERING` / `GENERAL` and subscribes to any number of `ExamCycle`s (e.g., `jee-main:2027:s1`, `neet-ug:2027`, `nda:2027:i`, `gate:2027`, `upsc-ese:2027`, `ssc-je:2026`).
2. A configured official-source watcher periodically checks a listing, discovers a **new URL or changed content hash**, records the evidence, and creates `DetectedNotice` with `review_status=DETECTED`.
3. The ingestion layer classifies the notice. `SourceGate` verifies configured source lineage; the operator reviews unverified or ambiguous changes. For MVP, **all notifications require review approval**.
4. Approved informational notices route to subscribers by exam cycle + topics. Approved amendments affecting one of five supported rule types also cause deterministic profile evaluation; missing facts result in `UNKNOWN`, not guesses.
5. An `InAppNotification` is persisted per recipient (`update_id`, `user_id` unique); user sees evidence/source link, personalized relevance, language and disclaimer. Admin sees only actual aggregates.
6. Existing PDF upload is an **operator fallback/testing tool**; ordinary subscribers never have to upload documents.

## 2. Major concept distinctions

| Concept | Meaning | Important constraint |
|---|---|---|
| `ExamCatalogEntry` | JEE Main, NEET UG, NDA, GATE, ESE, SSC JE, etc. | Not tied to a particular year |
| `ExamCycle` | JEE Main **2027 Session 1** vs Session 2 | All notices/subscriptions scoped to correct cycle |
| `OfficialSource` | Configured official listing page/adapter | An official-looking hostname ≠ authenticated PDF |
| `DetectedNotice` | Discovered source item with immutable evidence | Not an approved alert |
| `NoticeUpdate` | Reviewed, publishable announcement | Informational updates allowed without a RuleChange |
| `NoticeChange` | A supported *rule* amendment | Five types only; reference and evidence required |
| `ExamSubscription` | User opts into an exam cycle and topics | User may subscribe without sensitive profile data |
| `RecipientMatch` | Engine-computed relevance to one subscriber | `PERSONAL_IMPACT` only when actual status transition computed |
| `InAppNotification` | Persisted user-visible delivery event | Source link and evidence required |
| `AdminDashboardTotals` | Database-derived operator metrics | No invented counts |

Use `SourceKind.LOCAL_DEMO_FIXTURE` for demo playback, and show `SYNTHETIC DEMO` on screen. Do **not** portray it as a fetched official update.

## 3. General HTTP conventions

- Prefix: `/api/v2`. JSON UTF-8. ISO 8601 timestamps with timezone offset (`Z` allowed). Dates `YYYY-MM-DD`. Pagination: opaque `next_cursor`.
- API errors: `{ "code": "...", "message": "...", "request_id": "...", "details": {} }`, response HTTP status appropriate to cause. Use `409 CONFLICT` for stale admin revision/idempotency collision; `422` for malformed schema; `403` for wrong role; `404` for missing/private resource; `503` for source/Sarvam unavailable. No silent success.
- `schema_version="2.0.0"` on list/summary responses. `Content-Type: application/json`.
- Authentication: routes named `/me` require logged-in user, other user IDs must be derived from token/session on backend—not accepted from untrusted client. `/admin` routes require operator role.
- **Public read vs admin:** Catalog is public; source controls/review/dashboard are admin-only; personal data/notifications private. Never expose other users' names/DOB in admin aggregate responses.
- Source note: matching an allowlisted URL means `MATCHED_CONFIGURED_SOURCE`, never "officially authenticated". Avoid trusting AI-generated source attributions.
- Write operations: use server-generated IDs and deterministic idempotency key. Any amendment application must be revision-checked and atomic.

## 4. Planned endpoints — phase 1

| Method | Path | Request | Response | Who |
|---|---|---|---|---|
| GET | `/api/v2/catalog` | optional `audience`, `search` | `CatalogResponse` | public |
| GET | `/api/v2/me/subscriptions` | none | `ExamSubscription[]` | user |
| POST | `/api/v2/me/subscriptions` | `{cycle_id, topics, application_status}` | `ExamSubscription` | user |
| PATCH | `/api/v2/me/subscriptions/{subscription_id}` | `{topics?, application_status?, notifications_enabled?}` | `ExamSubscription` | owner |
| DELETE | `/api/v2/me/subscriptions/{subscription_id}` | none | 204 | owner |
| GET | `/api/v2/me/notifications` | `cursor?, limit?, unread_only?` | `NotificationsResponse` | user |
| POST | `/api/v2/me/notifications/{notification_id}/read` | none | `InAppNotification` | owner |
| GET | `/api/v2/me/profile` | none | `UserProfileV2` | user |
| PATCH | `/api/v2/me/profile` | opt-in and optional self-reported fields | `UserProfileV2` | user |
| DELETE | `/api/v2/me/profile/personalization` | none | 204 | user |
| GET | `/api/v2/admin/dashboard` | none | `AdminDashboardResponse` | admin |
| GET | `/api/v2/admin/sources` | none | `OfficialSource[]` with health separately | admin |
| GET | `/api/v2/admin/notices` | `review_status?, cycle_id?, cursor?` | `DetectedNotice[]` | admin |
| POST | `/api/v2/admin/notices/{notice_id}/review` | `NoticeReviewDecision` | reviewed `DetectedNotice`, then update created if approved | admin |
| POST | `/api/v2/admin/monitor/{source_id}/check` | `dry_run=true` (default) | `MonitorCheckResult` (to be designed before implementation) | admin |
| GET | `/api/v2/admin/updates/{update_id}/recipients` | `cursor?` | `RecipientMatch[]`, privacy-restricted | admin |

**Implementation status:** all phase-1 subscription/profile/inbox/admin endpoints above are implemented in this repository. The monitor check response is now defined below. The original supplied kit was contract-only; this is the merged implementation contract. Evidence-backed personalized v2 rule-change publication is implemented for the five closed rule types; section 13 records its supported scope and conservative review holds. The Sarvam text/OCR increment is specified in section 12.

## 5. Example payloads (SYNTHETIC; illustrate shape, not real alerts)

Catalog item:

```json
{
  "exam_id": "jee-main",
  "display_name": "JEE Main",
  "exam_family": "SCHOOL_ENTRANCE",
  "audiences": ["SCHOOL"],
  "organizer": "National Testing Agency",
  "description": "Engineering entrance examination",
  "active": true,
  "source_ids": ["nta-jee-main"]
}
```

Subscription create body:

```json
{
  "cycle_id": "jee-main:2027:s1",
  "topics": ["REGISTRATION", "EXAM_SCHEDULE", "ADMIT_CARD"],
  "application_status": "PLANNING_TO_APPLY"
}
```

Notification (synthetic; actual API response must be Pydantic-validated):

```json
{
  "notification_id": "notif-demo-1",
  "user_id": "user-demo-1",
  "match_id": "match-demo-1",
  "update_id": "update-demo-1",
  "cycle_id": "jee-main:2027:s1",
  "delivery": "DELIVERED",
  "headline": "JEE Main: application window changed (SYNTHETIC DEMO)",
  "body": "A source-linked update affects an exam you follow. Open the official notice for details.",
  "language": "en",
  "created_at": "2026-10-30T12:00:00Z",
  "delivered_at": "2026-10-30T12:00:01Z",
  "read_at": null,
  "official_source_url": null,
  "evidence": [{
    "document_id": "doc-demo-1",
    "document_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "page_number": 1,
    "literal_quote": "Synthetic testing clause only."
  }],
  "disclaimer": "Decision support only; not official eligibility or application confirmation."
}
```

## 6. Event/review state machine

```text
Source listing / admin fixture
   -> DETECTED -> PROCESSING -> NEEDS_REVIEW
                        |                |
                        v                +--(operator rejects)--> REJECTED
                     FAILED              +--(source mismatch)----> QUARANTINED
                                         +--(approve)------------> APPROVED
                                                                    |
                                         immutable NoticeUpdate + recipient matching
                                                                    |
                                           notification QUEUED -> DELIVERED -> READ
                                                               \-> FAILED (retry)
```

Never dispatch from `DETECTED`, `PROCESSING`, `NEEDS_REVIEW`, `QUARANTINED`, or `FAILED`. Approval should be recorded with `reviewer_id`, `reviewed_at`, decision reason, and revision. If an approved update later needs correction, publish a new correction event; do not silently mutate delivered notifications.

## 7. Matching logic (deterministic; avoid fanout LLM calls)

1. Match notice to **one or more explicitly mapped** exam cycles. When uncertain, `NEEDS_REVIEW` instead of mass-broadcast.
2. Map notice type to topics: deadline/application changes -> `REGISTRATION`; date change -> `EXAM_SCHEDULE`; admit card -> `ADMIT_CARD`; result -> `RESULTS`; etc. A topic `ALL` receives all approved notices for its cycle.
3. Match active subscriptions. Remove duplicates by `(update_id, user_id)` even if user tracks multiple topics.
4. For general news, `relevance=GENERAL_UPDATE` and **no** `before`/`after` decisions.
5. For supported validated rule amendments and profile opt-in, invoke pure Python rule evaluator. Mark actual state changes `PERSONAL_IMPACT`, incomplete profile or coverage `POSSIBLE_IMPACT` / `UNKNOWN`. Never interpret unsupported exemptions as PASS.
6. Persist recipient matches and notifications with an idempotent outbox transaction. Update real counts only after DB commits; delivery/read status is distinct from *matched*.

## 8. Data / effective-date / evidence policy

- Preserve old v1 rule engine/evidence DTOs from `backend/legacy_schemas_v1.py` while migrating. The new `NoticeChange.proposed_rule` uses the five-rule v1 discriminated union; map `legacy.RuleBase.scheme_id` to `ExamCycle.cycle_id` in application code, document this mapping in tests.
- `published_on` (source claim) vs `first_seen_at` (fetch timestamp) vs `effective_from` (operative rule date) are distinct. For late publication/effectivity, no unreviewed backdated flip.
- A supersession requires an explicit reference/target and applicable scope, or review. Newer notice ≠ entire rule set replaced.
- Actual `EvidenceAnchor.literal_quote` must match a stored immutable extracted page text; fields/offsets are rejected if mismatched. Where OCR position is unreliable, show page and quote only.
- Source page and URL must be displayed on the user notification and admin details.
- In-app notification text, Hindi explanatory text, and any audio numbers/dates must be validated against canonical values, otherwise suppress unsupported assertions.

## 9. Frontend views

**User:** exam catalog search/filter (school/engineering/general) -> multi-cycle subscription -> personal notification inbox -> notice detail with original link and summary; optional, opt-in profile page. Show clear `No updates yet`, `Demo data`, `Source unavailable` and `Unknown relevance` states.

**Admin:** live source-health table -> detected/review queue -> approval+quarantine -> recent updates -> per-update recipients and computed before/after counts -> notifications delivered/failed/read; PDF/source evidence inspector, audit, synthetic evaluation scorecard. No misleading "official admin" branding.

**90-second demo:** one genuine source poll (or plainly labeled captured snapshot if network fails), review update, calculate synthetic subscribers, persist alerts, switch to user inbox, show source citation, return to actual admin aggregates. Real personalization only for supported constraints.

## 10. Change control

`backend/schemas.py` and this markdown are a paired interface contract. When updating fields or enums, update both, add tests, bump schema version when breaking, preserve old code until consumers migrate, and update `PROGRESS.md` with commands/results. No silent magic conversions on API boundaries.


## 11. Implemented local-slice additions and boundaries

Public schema remains `2.0.0` for this first v2 implementation. V1 remains schema
`1.1.0` and retains its own `error_code` error shape. V2 errors use `code`.

### Added request/result DTOs

- `SubscriptionCreate`: `cycle_id`, unique nonempty `topics` (default ALL),
  `application_status` (default INTERESTED). `SubscriptionPatch`: optional topics,
  application status and notifications enabled. ALL is exclusive.
- `ProfilePatch`: optional language/display name, opt-in and self-reported personal
  fields. Personal values still require opt-in in the final merged UserProfileV2.
- `DemoSessionRequest`: persona SCHOOL/ENGINEERING/OPERATOR expressed as lowercase
  `school`, `engineering`, `operator`. `SessionResponse`: access token, server-owned
  user ID, display name, USER/ADMIN role, demo_mode=true and aware expiry.
- `MonitorCheckRequest`: `dry_run=true` default. `MonitorCheckResult`: schema version,
  source ID, check timestamp, dry-run flag, LIVE/OFFLINE_REPLAY mode, listing SHA-256,
  discovered/created/duplicate counts, unmapped-item reasons and errors.
- `SourceHealth`: DISABLED/NEVER_CHECKED/LIVE_OK/ERROR/OFFLINE_REPLAY, attempt/success
  timestamps, last error/HTTP status, new/total notice counts, robots result and
  next due time. It reports observations, not cryptographic authenticity.
- `NoticeDetail`: typed notice, extracted pages, listing URL, observed link title
  and extraction version. `InboxItem`: notification, actual recipient match,
  published update and originating notice.
- `PlatformStatus`: schema version, actual demo mode, Sarvam NOT_CONFIGURED or
  NOT_TESTED, and disclaimer. This does not certify credentials or API success.

Additive fields: EvidenceAnchor has optional `extraction_id` (populated and required
by this service's publication gate); DetectedNotice has `revision`, `topics`,
`processing_mode` (SOURCE_EXCERPT/OFFLINE_REPLAY/SARVAM_105B/NEEDS_EXTRACTION),
`diagnostics` and `requires_rule_validation`. CatalogResponse has server-owned
`coverage` by exam: CATALOG_ONLY/SOURCE_CONFIGURED/LIVE_MONITORED. Coverage requires
an enabled tested adapter, successful source health and recent worker heartbeat
before claiming live monitoring. It is not an open-registration or full-coverage
claim. NotificationsResponse adds backend-calculated `unread_count`.

AdminDashboardTotals adds `notifications_read`. AdminDashboardResponse adds typed
`source_checks`, database-derived `by_cycle` subscription/update/notification
counts, `synthetic_demo`, and `monitor_running` based on a recent worker heartbeat.
The older `source_health` string mapping is retained.

### Additional routes

| Method/path | Result / authorization |
|---|---|
| GET `/api/v2/status` | PlatformStatus; public |
| POST `/api/v2/demo/session` | DemoSessionRequest → SessionResponse; loopback-only, explicitly local demo mode |
| GET `/api/v2/me/notifications/{notification_id}` | InboxItem; owner only, 404 for another user's record |
| DELETE `/api/v2/me/account` | 204; learner owner, cascades private data and revokes sessions |
| GET `/api/v2/admin/notices/{notice_id}` | NoticeDetail; operator only |
| POST `/api/v2/admin/demo/replay` | DetectedNotice[]; operator and demo mode only, explicitly synthetic, never auto-publishes |

The review route requires the body notice ID and reviewer ID to match the URL and
actual operator session. The server's own clock records approval; client timestamps
are not authoritative. `(notice_id,expected_revision)` plus canonical request hash
provides idempotency: exact retries return the stored response, conflicting reuse
returns 409. No duplicate publication or dispatch occurs.

### Persistence, evidence and delivery

Additive `v2_*` tables share SQLite with the preserved v1 Store. A separate v2
migration ledger avoids changing the v1 database version. Source captures and
extractions are immutable. The extraction identity binds raw source SHA-256 and
extractor version; evidence binds that identity, exact page and offsets. Review
rechecks source bytes, immutable extraction checksums and source-listing lineage.
No arbitrary uploaded trust flag is accepted from a subscriber.

Notice dedup is unique by source/canonical URL/meaningful-content hash (cycle,
observed title, extractor version and frozen page text). Actual raw byte SHA-256
is stored separately and retained in evidence. This prevents a footer visitor
counter or PDF metadata-only change from manufacturing a new substantive alert.

A review transaction writes approval, immutable NoticeUpdate, RecipientMatch and
DELIVERED in-app notification rows together, or rolls all of them back. In-app
DELIVERED means the owner's persisted inbox row exists; no push/email/SMS delivery
is implied. Uniqueness `(update_id,user_id)` prevents duplicate alerts. No per-user
LLM is used. Informational updates have GENERAL_UPDATE with null decisions.
Notices requiring personal-rule validation are held until the v2 bridge exists.

Inbox cursors are signed and owner-bound; results are newest first. Mark-read is
idempotent. Subscriptions may be paused or marked NO_LONGER_INTERESTED; those do
not receive new alerts. APPLIED_SELF_REPORTED is never verified application status.

### Monitoring and deferred work

Only NTA JEE Main and UPSC active exams have implemented, genuinely exercised
adapters. See `docs/SOURCE_VERIFICATION.md`. Checked-in registry defaults remain
disabled; runtime enablement follows a successful real check. Exact HTTPS host,
DNS/public-address and redirect checks precede bounded fetches. Robots is inspected;
nonstandard UPSC behavior is recorded explicitly. Sources use hourly polling,
reported failure states and rate-limit cooldowns. The standalone worker and the
API background worker run independently of the frontend. Run one worker mode at a
time. Each poll downloads at most five mapped documents; older/unmapped cycles
are recorded as unmapped, never broadcast to current-year subscribers.

A dry run may record a real fetch/capture/health observation but creates no notices,
updates or notifications. Failure returns typed 503; an enabled source that is not
yet due returns 429 with its next scheduled time. Only approved notices publish.

There is no production login provider, free-form Hindi/audio evaluation, v2
personalized rule-change publication, benchmark scorecard or deep attachment
crawler. Section 12 supersedes the initial slice with live Sarvam text/OCR and
controlled Hindi overviews. Existing v1 deterministic tests and
APIs remain operational. Local demo personas are not a public authentication scheme.


## 12. Sarvam text phase (additive v2.0.0 contracts)

`POST /api/v2/admin/notices/{notice_id}/analyze` accepts AnalysisRequest
`{expected_revision}` and returns NoticeAnalysis. Operator only. It does not approve
or dispatch. Stale source/revision or existing publication returns 409. Provider
configuration, quota, transport or credit-budget failures return typed 503 errors.
`GET /api/v2/admin/sarvam` returns SarvamHealth: observed status, model, local budget
limit/reservations in integer paise, request/token counts, last success/error.
PlatformStatus.sarvam_status now also admits LIVE_OK and ERROR.

SarvamCandidate contains exact cycle_id, notice_type, topics, requires_rule_validation
and 1–6 ExtractedFacts. Each fact has a closed kind (ANNOUNCEMENT,
APPLICATION_DEADLINE, EXAM_DATE, RULE_CANDIDATE, UNSUPPORTED_REQUIREMENT), 1-based
page_number, literal_quote and nullable ISO date_value. No decision, recipient,
source-trust or approval fields are accepted. Quotes, topic support and dates are
checked against immutable source text in Python. Unsupported/ambiguous rule
candidates stay held. This DTO is not a committed RuleDefinition.

NoticeAnalysis records analysis_id, notice_id, SARVAM_105B provider/model,
prompt_version, timestamp, VALIDATED/GUARD_REJECTED, cache_hit, input_sha256,
extraction_id, pages_processed, total_pages, coverage_complete, nullable candidate,
English/Hindi summaries, exact evidence and diagnostics. NoticeDetail.analysis is
nullable. summary_method is EXTRACTIVE_EN_CONTROLLED_HI: English quotes and controlled
Hindi labels/date statements, not an unchecked generated translation. A partial
input is explicitly labeled and never presented as full-document processing.

The immutable cache key includes raw-source hash, extraction identity/text hash,
model, prompt/guard version, cycle/title and actual selected input. No per-user model
calls. Paid requests reserve integer paise atomically against an explicitly set
local budget before HTTP. Reservations remain charged locally after errors/timeouts;
reported amounts are conservative admissions, never fabricated provider bills.
Requests have fixed model, bounded input/output, no credential logging, no automatic
retries of uncertain requests, and provider failures do not mutate committed rules,
reviews or notifications. Cached candidates are revalidated at use/publication.
Approved localized summaries are frozen in NoticeUpdate; language preference chooses
only between those reviewed summaries. Original literal evidence remains available.


NoticeAnalysis.guard_version records the exact span resolver/validator version.
Cached provider outputs are reprocessed when this changes, without another paid
request. A model-folded quote may be resolved only when all non-whitespace characters
match and there is exactly one contiguous matching span on that page; stored
literal_quote and offsets are the actual original text, not the folded AI string.
The current provider schema requests literal ANNOUNCEMENT/RULE_CANDIDATE/
UNSUPPORTED_REQUIREMENT facts with null date_value; Python date guards remain
available but no ambiguous numeric date is normalized by the model.


### OCR recovery for poor embedded text

POST `/api/v2/admin/notices/{notice_id}/ocr` accepts AnalysisRequest and returns
OcrResult (notice_id, nullable job_id, PENDING/COMPLETED, cache_hit, page count,
nullable extraction_id, provider SARVAM_VISION). Operator-only and revision-checked.
It submits at most five PDF pages within the same explicit Sarvam budget, persists
the job before polling, and resumes existing jobs instead of resubmitting. Only a
fully completed output with exactly the original 1-based pages may replace the
current extraction projection. Raw bytes and earlier extractions remain immutable.
OCR is not source authentication or human review. No boxes are claimed verified.
A stale result is cached without overwriting a changed/reviewed notice. Analysis
from a different extraction is hidden and must be rerun on the corrected text.


Scanned/no-text PDFs are retained as NEEDS_EXTRACTION with empty evidence and
immutable page/source records. They cannot publish or enable a source adapter until
text is recovered. OCR can verify raw lineage with an empty-text extraction; the
language-model path refuses empty input without spending credits. The observed
Document AI server returns type=digitise with 1-based page_num, ordered text blocks
and HTML tables; this is parsed explicitly alongside the documented per-page
content shape. A versioned deterministic HTML-to-text extraction is frozen before
language-model processing. OCR page text is not independently verified against
pixels and always requires operator comparison with the original PDF.

A GUARD_REJECTED analysis bound to the current extraction blocks publication with
409 ANALYSIS_GUARD_BLOCKED, including direct API attempts. The operator can quarantine
or reject; correcting the source/extraction and reprocessing is required to publish.

Controlled Hindi templates additionally recognize a closed set of exact source labels
(notification date, examination commencement, application receipt deadline, upload
date), copying the original value/format verbatim. They do not infer an ISO rule,
calendar interpretation or timezone from ambiguous numeric dates.


## 13. Future-plan phases 1–3 contract update (additive v2.0.0)

NoticeAnalysis adds `notice_changes: NoticeChange[]` and `rule_set_revision: int`
(default zero). These are server-derived proposals, never model authority. The
supported rule subset requires literal explicit Published/Effective/Scheme/
Operation/(Target for REPLACE/REVOKE)/Scope context and a closed EN/HI condition.
Missing/ambiguous scope, targets, dates or unsupported mixed batches stay held.
No fallback to today, first-same-type targets or document-name substitution exists.
New stable IDs derive from source notice/context. Publication recomputes proposals
from immutable source facts and independently verified lineage, checks the cycle
revision, then supplies explicit attestations to the unchanged v1 planner.

Migration 005 appends immutable full rule-history snapshots and maintains a
cycle revision/hash head. Closed/revoked intervals are retained in each complete
snapshot, so loading after restart reproduces the planned rule hash and decisions.
Draft migration-004-only rule data requires review rather than guessed conversion.
Schema version remains 2.0.0 for these additive fields; v1 contracts stay 1.1.0.

`POST /api/v2/admin/sarvam/credit-balance` (operator only) accepts
`{credits: "598.12"}` from a freshly refreshed dashboard. SarvamHealth adds
`credit_safety` with fixed 50000-hundredth floor, reported/estimated balances,
report/expiry timestamps and `paid_requests_allowed`. Missing, stale, wrong-key,
insufficient-balance snapshots block new paid operations atomically. The existing
5000-paise lifetime local reservation cap remains independent. Successful/failed/
uncertain reservations are retained. Cached processing remains available. This is
an explicitly manual organisation-balance observation, not a live balance API.
Shared spending by other products/keys cannot be measured by this local ledger.

MonitorCheckResult and SourceHealth add `pending_extractions` (default zero).
Listing fetch success and deferred OCR are separate states; adapter enablement
requires at least one usable mapped extraction and no fetch/structure errors.
Blank PDFs remain held with no publication path until OCR/evidence verification.

`GET /api/v2/admin/processing` returns persisted ProcessingQueue jobs/counts and
freshness-based worker_active. `POST /api/v2/admin/processing/{notice_id}/retry`
queues an operator retry within the three-attempt limit. Queue states are QUEUED,
LEASED, RETRY, PAUSED, REVIEW_READY, HELD, COMPLETE. Five-minute leases use unique
ownership tokens. Lost leases/uncertain paid submissions pause for reconciliation.
Rate-limit/conflict retries are bounded; missing credits/budget pause admission.
Workers never approve a notice or send notifications. Root lists rotate in batches
of five, UPSC PDF attachments in batches of two per detail page. Attachments require
an immutable root-listing → exam-detail → observed-PDF lineage, verified at review.

User-facing v2 disclaimer default is `Decision support only; not official approval.`
The retained v1 intake still limits PDFs to 20 pages. Official v2 PDF extraction
accepts at most 100 readable pages / 2 MiB embedded text under the existing 10 MiB
HTTP bound, so the observed 62-page UPSC bulletin can be preserved and cited.
105B remains limited to six pages / 30 KiB; partial coverage is shown and never
makes unsupported rules operative. Speech and exact coordinate highlights are
not implemented in these phases.

InAppNotification also accepts the earlier v2 disclaimer literal when loading
saved alerts. Historical notification payloads are preserved without rewriting.


## Real-account release (additive contracts; cookie authentication)

Default runtime no longer creates demo users or exposes role switching. Test-only
DemoSessionRequest remains available only under explicit local demo mode; production
mode refuses to enable it. Existing v1 code is preserved; its private operations
now require an authenticated administrator and CSRF protection in the real runtime.

Public routes: GET /api/v2/auth/config (AuthConfig), GET /api/v2/updates
(PublicUpdatesResponse, reviewed OFFICIAL_WEB_LISTING updates only), and
GET /api/v2/sources (PublicSource[] with measured coverage/check timestamps).
No subscriber identities, keys, processing internals or unreviewed summaries are public.

Accounts:
- POST /auth/register: RegisterRequest {email, display_name?, adult_confirmed:true}.
  202 EmailActionResponse means REQUEST_ACCEPTED, never guaranteed delivery.
- POST /auth/resend-verification and /auth/forgot-password: EmailRequest; generic 202.
- POST /auth/verify and /auth/reset-password: CompleteAccountRequest {token,password}.
  Tokens are purpose-bound, expiring and single-use; passwords are chosen only by
  the mailbox holder, 15–128 characters, with spaces preserved. Returns AuthSession.
- POST /auth/login: LoginRequest {email,password}; returns AuthSession.
- GET /auth/session restores AuthSession; POST /auth/logout revokes it.
- POST /auth/password: PasswordChangeRequest {current_password,new_password}; 204,
  all sessions and unused action tokens revoked. DELETE /me/account requires
  AccountDeletionRequest {password} for real learner accounts; administrator accounts
  cannot be deleted through that learner endpoint.

AuthSession exposes user_id, email, display_name, USER/ADMIN role, email_verified,
expires_at and a CSRF token. It never exposes the authentication/session cookie value.
Opaque session IDs and email tokens are hashed at rest; Argon2id hashes passwords.
Session lifetime is eight hours with thirty-minute idle expiry. Secure production
cookies use __Host-niyampulse, HttpOnly, Secure, SameSite=Lax, Path=/ and no Domain.
Local HTTP uses niyampulse_session with HttpOnly and SameSite=Lax. Cross-origin unsafe
requests are refused; cookie-authenticated mutations require X-CSRF-Token. Cookies
and browser bearer tokens are not stored in localStorage. Real roles are assigned
only by the trusted server CLI, not registration input or a UI selector.

Production mode requires an HTTPS canonical NIYAMPULSE_PUBLIC_URL; local HTTP is
limited to loopback. Mail uses configured SMTP with STARTTLS or implicit TLS; no
placeholder sender/provider is used. Missing SMTP disables registration/recovery.
Authenticated SMTP requires a complete username/password pair; an incomplete pair
also leaves both AuthConfig availability flags false and registration/recovery at
503. Explicit unauthenticated TLS relays are supported. Configured does not mean
the provider has authenticated successfully or an email has reached its inbox.
Email links carry action tokens in fragments, cleared from browser history before
rendering. Request bodies for /auth are capped at 8 KiB, including chunked bodies;
authentication/email requests use persisted rate limits. Security headers, host
validation and no-store private responses are enabled.

Initial account registration requires an adult holder's self-declaration; a guardian
may follow exams without adding a child's details. This is not verified age or
parental-consent verification. Direct child accounts and public deployment require
separate policy/consent readiness; no child DOB is collected during account setup.

New real subscriptions receive at most twenty reviewed informational updates from
the last thirty days, filtered by cycle/topics, deduplicated by (update_id,user_id).
Rule-update history is not replayed as a new personal before/after assessment.

The production store is var/production/niyampulse.sqlite3. A one-time backed-up
migration preserves genuine source snapshots, extractions, approved history and the
entire Sarvam reservation/cache ledger. Synthetic accounts, subscriptions, inbox
records, notices and v1 fixture workspaces are excluded. The old database remains
an archive; no real users or default administrator passwords are fabricated.

## Deployment and operational contract — 31 October 2026

- New v2 notification defaults and visible v2 UI use the required disclaimer:
  `Decision support only; not official eligibility or application confirmation.`
  Existing v1 payloads and historical source/audit records remain unchanged.
- Public `GET /api/v2/health/live` and `GET /api/v2/health/ready` return
  `ServiceHealth {schema_version:"2.0.0",status:"OK"|"NOT_READY",checks:Record<string,boolean>,monitoring_enabled:boolean}`.
  Readiness verifies the database/account migration, built frontend and required
  worker threads. It returns HTTP 503 on failure; liveness returns 200. These
  operational statuses are separate from deterministic applicant decision states.
  No account identities, database paths, credentials or raw exceptions are returned.
- API write bodies are bounded before parsing: 8 KiB for `/auth`, 256 KiB for
  other JSON operations, and 10 MiB PDF plus 64 KiB multipart overhead on legacy
  document uploads. Overflow returns HTTP 413 in the appropriate v1/v2 ApiError.
- Unknown NIYAMPULSE_ENV values fail startup. Render/Vercel environments default
  to production and refuse explicit local mode. Render can derive its canonical
  HTTPS origin from RENDER_EXTERNAL_URL if NIYAMPULSE_PUBLIC_URL is unset.
- Production runtime requires an explicit absolute data directory, a verified
  durability declaration, complete SMTP configuration, and disabled demo flags.
  On Render, the data path must be inside an actual persistent disk mount. The
  SQLite/worker backend refuses Vercel serverless execution. Production API and
  standalone worker share an OS-owned lock; use one runtime, not multiple workers.
- Interactive API docs/OpenAPI HTTP routes are disabled in production; schema
  generation through Python remains available. Hashed frontend assets are immutable
  cached; HTML revalidates and API responses remain no-store.
- Verified online backups include source evidence, accounts and the entire
  financial/cache ledger. Restore verifies its SHA-256 manifest, requires a new
  destination and revokes all sessions/action tokens. It never overwrites live data.
  Operational preflight is a local check, not evidence of a hosted deployment.

## Sarvam policy update — 31 October 2026

The user removed the local INR 50 cap while retaining the 500-credit reserve.
`SarvamHealth.budget_limit_paise` is now `integer | null`; null explicitly means
no local INR cap. The persistent metadata flag `sarvam_budget_uncapped=1` enables
this mode without deleting reservations or changing the provider key. Finite caps
can be restored through the operator CLI. `backend.analyze --uncapped` changes only
this policy; it does not submit work. The 15-minute manually refreshed balance,
per-call reservation, single-source limits, evidence guards and human review remain.
This is not unrestricted key exposure or automatic source approval. Keys stay on
the backend. Sarvam-105B, Vision and the bounded Saaras/Bulbul routes below are implemented.

## Final feature increment — source detail, accessibility and evaluation

- RecipientMatch adds `before_checks`/`after_checks` arrays of the preserved v1
  RuleCheck DTO (default empty for historical alerts). New rule-change matches
  persist actual engine checks; unchanged overall states may still have evaluated
  checks. A transition animation requires non-null, different overall states.
- Profile settings expose explicit opt-in adult-own DOB, marks, integer INR income
  and document codes/inventory completeness. Real-runtime personal DOB under 18 is
  refused; guardians must not enter a child's data. Erasure/opt-out remains usable.
- AuthConfig adds optional public `support_email`; configured through
  PUBLIC_SUPPORT_EMAIL. Owner explicitly authorized their Gmail as public contact.
- POST `/api/v2/me/voice-search`: authenticated, CSRF protected, multipart `file`,
  mono PCM WAV 16 kHz/16 bit, <=25 sec and <=1 MiB. Returns VoiceSearchResult
  {transcript,language_code,exam_ids,action_taken:false}. Saaras:v4 only transcribes;
  suggested catalog matches never subscribe/change an account automatically.
- POST `/api/v2/me/notifications/{id}/audio`: owner only; POST
  `/api/v2/admin/notices/{id}/audio`: admin preview of an already approved update.
  Returns NoticeAudio {text,audio_base64,content_type:"audio/wav",cache_hit,model}.
  Bulbul:v4-flash receives only reviewed text after exact-summary, numeric/date and
  informational-status guards. No arbitrary client synthesis text. Recordings are
  not persisted; source-only generated audio is cached. All live calls share the
  existing reservation ledger/500-credit floor. Failure does not auto-retry.
  Microphone is permitted for self origin, with explicit browser/user activation.
- Authenticated cached source PDF and PNG page endpoints are available under
  `/admin/notices/{id}` and `/me/notifications/{id}` at `/source.pdf` and
  `/pages/{1-based-page}.png`. Source hashes are verified before rendering. PNG
  response X-Verified-Highlights counts exact native-text matches; OCR-only or
  unmatched text receives no invented highlights. HTML sources retain official
  links and literal excerpts rather than being served as executable HTML.
- POST `/api/v2/admin/evaluations` runs the actual built-in synthetic text parser,
  amendment planner and deterministic evaluator, compares supplied gold and repeats
  replay. GET `/admin/evaluations/latest` returns EvaluationReport or null. Reports
  are persisted separately from production notices/people. No scorecard before a
  run; the scope is declared synthetic transition/count/replay agreement, not OCR,
  model/source authenticity accuracy, baseline superiority or official eligibility.
