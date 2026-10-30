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

**Implementation status:** all phase-1 subscription/profile/inbox/admin endpoints above are implemented in this repository. The monitor check response is now defined below. The original supplied kit was contract-only; this is the merged implementation contract. Personalized v2 rule-change publication remains unimplemented. The Sarvam text/OCR increment is specified in section 12.

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
