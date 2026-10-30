# SHARED_CONTRACTS.md — Frontend ↔ Backend Handshake

**Project:** NiyamPulse LIVE  
**Contract version:** `1.0.0`  
**Source of truth for DTO shapes:** `backend/schemas.py` (Pydantic v2)  
**Target runtime:** Python 3.12 (native Windows), FastAPI; React + TypeScript + Vite frontend  
**Status:** **SPECIFIED ONLY** — HTTP endpoints and frontend are **not implemented** in this starter.

> This is the cross-team agreement. The frontend may animate data received from the backend, but may not calculate eligibility, infer source trust, invent impact counts, or alter effective rules.

## 1. Transport and conventions

| Concern | v1 contract |
|---|---|
| Base URL (development) | `http://127.0.0.1:8000/api/v1` |
| Allowed dev origin | `http://localhost:5173` (configure CORS explicitly) |
| Content type | `application/json; charset=utf-8`, except PDF/audio uploads and streamed media |
| Naming | JSON `snake_case`; TypeScript may use the same names to avoid accidental drift |
| API version | `/api/v1` path plus `schema_version: "1.0.0"` on versioned top-level state/results |
| Timestamp | ISO 8601 with offset; server emits UTC `Z`, e.g. `2026-10-30T12:00:00Z` |
| Date-only values | `YYYY-MM-DD`, interpreted as scheme-local calendar dates; default demo zone `Asia/Kolkata` |
| IDs | Opaque stable strings, not array indexes or filenames |
| Currency | Integer Indian rupees (`annual_household_income_inr`) |
| Marks | Numeric percentage `0..100` (`marks_percent`) |
| Pages | **1-based** `page_number` |
| PDF bounding boxes | Normalized coordinates `0..1`; top-left origin; `x0,y0,x1,y1` |
| Missing data | `null`/unknown is distinct from zero or empty; document inventory uses `document_inventory_complete` |
| HTTP errors | Non-2xx with typed `ApiError`: `{ "error_code", "message", "request_id", "details" }` |
| Ordering / concurrency | Use `revision` and `expected_workspace_revision` on apply; reject mismatches with HTTP 409 |
| Events | Poll initially; backend guarantees event IDs are stable, event feed returns an opaque cursor |

### Global states

- `DecisionStatus`: `PASS | FAIL | UNKNOWN | CONFLICT`.
- `IntakeState`: `RECEIVED | EXTRACTING | NEEDS_REVIEW | READY_TO_APPLY | APPLIED | QUARANTINED | FAILED`.
- `SourceMatchState`: `UNVERIFIED | MATCHED_CONFIGURED_SOURCE | MISMATCH`.
- `GateRecommendation`: `MANUAL_REVIEW | QUARANTINE | ALLOW_REVIEW`.
- `ReviewState`: `PENDING | APPROVED | REJECTED`.
- `ChangeOperation`: `ADD | REPLACE | REVOKE`.
- `ImpactDirection`: `IMPROVED | WORSENED | UNCHANGED | REVIEW_REQUIRED`.

The UI must show this exact disclaimer alongside overall outcomes:

> **Decision support only; not official approval.**

### Decision meanings

- `PASS`: all *verified, applicable* closed-set rule checks pass and at least one exists. **Not** official approval.
- `FAIL`: at least one relevant condition demonstrably fails, with no overriding unresolved conflict.
- `UNKNOWN`: a required profile value, rule source, or applicable rule set is missing.
- `CONFLICT`: competing operative rules or unresolved source/precedence evidence prevents a dependable result.

Aggregation precedence in the engine: `CONFLICT` > `FAIL` > `UNKNOWN` > `PASS`. If zero rules are verified and applicable, aggregate status is `UNKNOWN`.

Only a transition from overall `FAIL` to overall `PASS` is called `IMPROVED`, and only `PASS` to `FAIL` is `WORSENED`. Other uncertain transitions are `REVIEW_REQUIRED`. For unchanged overall status use `UNCHANGED`. `ImpactCounts.changed` means **number of profiles with changed overall status**; the per-rule details may change even when that count does not.

## 2. Planned HTTP endpoints

These routes are the **implementation target**, not evidence that a server currently exists.

| Method / route | Body / query | Response | Side effects |
|---|---|---|---|
| `GET /health` | None | `{ "status": "ok", "schema_version": "1.0.0" }` | None |
| `GET /workspaces/{workspace_id}` | None | `WorkspaceState` | None |
| `POST /workspaces/{workspace_id}/documents` | `multipart/form-data`: `file` PDF; `kind` (`ORIGINAL`/`CORRIGENDUM`); optional `source_url` | `ImportDocumentResponse`, HTTP **202** | Queue local extraction; does **not** apply rules |
| `GET /workspaces/{workspace_id}/amendments/{amendment_id}/preview` | None | `PreviewAmendmentResponse` | Calculate **PREVIEW** impact, never persist active rules |
| `POST /workspaces/{workspace_id}/amendments/{amendment_id}/apply` | `ApplyAmendmentRequest` | `ApplyAmendmentResponse` | Atomically review+apply approved amendment and emit impact event; **409** on stale revision |
| `GET /workspaces/{workspace_id}/timeline` | `as_of_date=YYYY-MM-DD`; optional `known_at=<ISO timestamp>` | `TimelineSnapshot` | None |
| `GET /workspaces/{workspace_id}/events` | Optional `cursor=<opaque>` | `EventFeedResponse` | None |
| `POST /workspaces/{workspace_id}/explanations` | `ExplanationRequest` | `VerifiedExplanation` | May cache verified explanation; never changes decision |
| `POST /workspaces/{workspace_id}/speech/transcribe` | `multipart/form-data`: `audio` (max 30s REST demonstration) | `TranscriptResponse` | May call Sarvam Saaras |
| `GET /assets/{audio_asset_id}` | None | Audio bytes (`audio/mpeg` or actual supported MIME) | None |
| `GET /workspaces/{workspace_id}/evaluations/latest` | None | `EvaluationScorecard` or HTTP **404** if no test run exists | None |

For import, an HTTP **202** means accepted for processing, **not** that OCR, authority checks, or rule application succeeded. Poll `GET /workspaces/{workspace_id}` for the latest intake state. For a scanned PDF with no usable OCR, keep it in `NEEDS_REVIEW`/`FAILED` and report a diagnostic; never produce fabricated rules.

### Apply preconditions (all must hold)

1. Amendment exists in the requested workspace, and its target original is explicitly identified.
2. The source gate returns `ALLOW_REVIEW` with **all checks passing** and `MATCHED_CONFIGURED_SOURCE`.
3. Human explicitly requests application (`confirm_source_review: true` and nonempty `reviewed_by`).
4. Candidate rule text, numerical values, evidence anchor, explicit target ID, scope, and effective dates passed validation.
5. No unresolved source conflict or unsupported rule type remains.
6. The supplied `expected_workspace_revision` equals the stored revision.
7. The server completes source review, version update, evaluation snapshot, and event persist **in one database transaction**, then returns the new revision.

`MATCHED_CONFIGURED_SOURCE` means a configured source-channel/reference check passed; it **does not certify cryptographic authenticity**. In a demonstration using synthetic PDFs, the UI must say so.

## 3. Canonical data structures

The names below correspond to Pydantic classes in `backend/schemas.py`. Generate TypeScript interfaces from the FastAPI OpenAPI document once the backend exists; do not independently reinterpret the classes.

| Shape | Important fields / invariant |
|---|---|
| `SourceDocument` | Immutable `document_id`, `sha256`, source URL, issuing authority, reference number, published date, acquisition timestamp, kind, OCR state |
| `SourceEvidence` | `document_id`, `document_sha256`, `extraction_id`, 1-based page, `literal_quote`; optional exact text offsets and PDF boxes |
| `RuleDefinition` | Discriminated union by `rule_type`, all with `rule_id`, `scheme_id`, `scope_key`, `effective_from`, exclusive `effective_until`, `evidence[]` |
| `MinimumMarksRule` | `min_marks_percent` numeric |
| `MaximumIncomeRule` | `max_annual_income_inr` integer |
| `ApplicationDeadlineRule` | `deadline_on` ISO date |
| `AgeBoundsRule` | `min_age_years`, `max_age_years`, **`age_as_of`** anchor date |
| `RequiredDocumentsRule` | `required_document_codes[]` nonempty and unique |
| `SourceGateResult` | Source match, recommendation, individually reported `checks[]` and check time |
| `AmendmentChange` | `operation`, `target_rule_id`, `proposed_rule`, `effective_from`, `amendment_evidence[]` |
| `AmendmentRecord` | Original/corrigendum IDs, gate result, review state, intake state, reviewed by/at, changes[] |
| `ApplicantProfile` | Marks, integer income, birth date, planned submission date, available documents and inventory completeness |
| `RuleCheck` | One rule's status, expected/observed values, reason code, source evidence |
| `ApplicantDecision` | Overall status and checks; `engine_version`, `rule_set_sha256`, disclaimer |
| `DecisionTransition` | One applicant's before/after `ApplicantDecision` plus `ImpactDirection` |
| `ImpactEvent` | `PREVIEW` or `APPLIED`, before/after rule hashes, backend-calculated counts, transitions[] |
| `TimelineSnapshot` | Effective rules and deterministic decisions on `as_of_date`; optional `known_at` filter |
| `VerifiedExplanation` | Source-backed sentences, rule IDs, source evidence, decision hash, numeric/date guard and optional audio asset ID |
| `EvaluationScorecard` | Synthetic dataset ID, run ID, actual numerator/denominator metrics, baseline measurements where present |

### Source evidence example

This is a **synthetic fixture**, not a real scholarship notice:

```json
{
  "document_id": "doc-corr-01",
  "document_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "extraction_id": "extract-01",
  "page_number": 1,
  "literal_quote": "Minimum qualifying marks shall be 70%.",
  "start_char": 145,
  "end_char": 183,
  "boxes": [ { "x0": 0.12, "y0": 0.24, "x1": 0.73, "y1": 0.29 } ]
}
```

The backend must not label such a quote **verified** merely because a model supplied it. It must verify that the quote is present in the extraction with the matching `(document_sha256, extraction_id, page_number)` and that the extracted rule value matches the quote. Character offsets are into the frozen page text for that extraction, not global concatenated text. The sample SHA and coordinates are placeholders and must never be represented as measured evidence.

### Rule candidate example

```json
{
  "rule_id": "rule-marks-v2",
  "scheme_id": "scholarship-demo-2026",
  "scope_key": "all_applicants",
  "effective_from": "2026-10-15",
  "effective_until": null,
  "evidence": [{
    "document_id": "doc-corr-01",
    "document_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "extraction_id": "extract-01",
    "page_number": 1,
    "literal_quote": "Minimum qualifying marks shall be 70%.",
    "start_char": 145,
    "end_char": 183,
    "boxes": []
  }],
  "rule_type": "minimum_marks",
  "min_marks_percent": 70.0
}
```

### Empty-but-valid initial state example

```json
{
  "schema_version": "1.0.0",
  "workspace_id": "scholarship-demo-2026",
  "revision": 0,
  "documents": [],
  "amendments": [],
  "active_rules": [],
  "profiles": [],
  "decisions": [],
  "latest_event": null
}
```

This state must render as **no verified decisions**, not as zero affected applicants with verified eligibility.

### Example apply request

```json
{
  "expected_workspace_revision": 4,
  "reviewed_by": "demo_operator",
  "confirm_source_review": true
}
```

Only the backend determines new decisions and emits `ImpactEvent`. The UI is not permitted to send applicant status changes or fabricated counts to the apply endpoint.

## 4. SourceGate and precedence policy

**Before rules are activated**, the backend checks:

- Is the intake origin a configured source, or merely a forwarded/unverified file?
- Does the claimed issuing authority match the expected scheme authority?
- Does the amendment's reference chain point to the *correct* original document?
- Are publication and effective dates parsable, explicit, and chronologically coherent?
- Does the change identify a supported operation and an unambiguous target rule and scope?
- Does each proposed value appear in its literal source passage, under an immutable extraction ID?

Check statuses are `PASS`, `FAIL`, or `UNKNOWN`. Any `FAIL` causes a quarantine recommendation. An unknown provenance condition requires manual review; do **not** auto-approve. A human reviewer is still required when all checks pass.

**Precedence:** an amendment is not a full replacement of the original document. `REPLACE` or `REVOKE` changes the effective interval of the targeted rule; unrelated rules remain. `ADD` may introduce a new scoped requirement but cannot silently coexist with a contradictory active rule. Document publication time and rule effective time are stored separately. `TimelineSnapshot.as_of_date` selects active rules by *effective* interval; when `known_at` is supplied, the view must also exclude documents not yet acquired by that time. Never assume a later published document is automatically operative.

## 5. Frontend state and interactions

### States and signals

| UI element | Backend-owned value | Rendering rule |
|---|---|---|
| Monitor badge | Local watch service health (future dedicated health data) | Show **LOCAL WATCHER** if only folder monitoring exists; never claim national real-time monitoring |
| Original/corrigendum cards | `SourceDocument` | Show ingestion/extraction state, provenance, acquisition date |
| Source trust ribbon | `AmendmentRecord.source_gate` | Amber on unverified, red on mismatch/quarantine; do not label proof of forgery |
| Applicant grid | `ApplicantDecision[]` | Four semantic colors/icons; never infer status from threshold in TypeScript |
| Shockwave | `ImpactEvent.transitions[]` | Animate affected actual overall state changes, not a hardcoded cohort count |
| Headline numbers | `ImpactEvent.counts` | Always server-calculated; `PREVIEW` clearly marked provisional |
| Date slider | `TimelineSnapshot` | Call backend for effective rules + decisions; do not mutate rules client-side |
| PDF inspector | `SourceEvidence` | Highlight boxes only if validated; otherwise show page + literal quote |
| Hindi text | `VerifiedExplanation.sentences[]` | Each sentence has rule IDs and evidence anchors |
| Hindi audio | `VerifiedExplanation.audio_asset_id` | Play only if `numeric_and_date_tokens_checked` is true; display cached/replay label where appropriate |
| Evaluation drawer | `EvaluationScorecard` | Hide score if no completed real test run; show `correct / total` and synthetic label |

**Color semantics (suggested design tokens):** background `#090F1C`, panel `#101A2B`, text `#F8FAFC`, secondary `#94A3B8`, accent cyan `#38BDF8`, PASS green `#4ADE80`, FAIL red `#F87171`, UNKNOWN slate `#94A3B8`, CONFLICT amber `#FBBF24`. Do not rely on color alone; use icons and labels.

### Shockwave sequencing

1. Frontend requests apply with the current revision and reviewed approval.
2. Server validates gate + evidence, commits rule change/evaluations, returns an **APPLIED** `ImpactEvent`.
3. Frontend updates the workspace from the server response and animates `transitions`.
4. Display changed, improved, worsened, and review-required counts from the event, never from a local mock.
5. Clicking a tile opens its `RuleCheck[]` and each source anchor.
6. On interruption, refresh state and deduplicate events by `event_id`; animations must not imply a second amendment was applied.

**Event-feed transport:** start with polling every ~2s using the opaque `next_cursor`; retry with exponential backoff; deduplicate by `event_id`. SSE/WebSockets are explicitly optional later.

## 6. Voice contracts and failure policies

- Saaras: capture a short clip with a visible recording indicator and request permission; ensure clip fits the documented REST limit. Show transcription before acting on it.
- The question is routed to source-backed retrieval/explanation only. Voice input **never** approves/amends rules without an explicit reviewed action.
- Explanation creation must pin `expected_rule_set_sha256` and reject stale requests (HTTP 409).
- Sentence references in `VerifiedExplanation` are programmatically resolved against the active decision's rules and source evidence.
- Numeric/date and entity checking must be performed after text generation and before Bulbul synthesis. If validation fails, replace generated text with a tested deterministic template or decline audio. The `audio_asset_id` field may be present **only** if the guard succeeded.
- Degraded modes are visible: `LIVE SARVAM`, `CACHED EXTRACTION`, or `OFFLINE REPLAY`. A prior audio file is identified as cached, not newly synthesized.
- API errors, OCR uncertainty, network timeouts, and malformed dates must never become silent PASS states.

## 7. Evaluation handshake

The scorecard reflects **measured** results from a reproducible synthetic test set, not hand-entered dashboard numbers.

- Generate 20+ synthetic original/corrigendum pairs, including English and Hindi/Devanagari, changed and unchanged rules, partial supersession, new document requirements, conflicting clauses, missing facts, authority/reference mismatches, and effective-date edge cases.
- Preserve gold labels: source text and spans; extracted rule types/values; target-rule mapping; applicable-rule set at a date; profile-level before/after statuses; and expected gate outcomes.
- Run the NiyamPulse pipeline against those fixtures; separately run a plainly documented baseline (e.g. a single unstructured LLM answer on the same text), with the same inputs and budget limits. Do **not** invent a baseline if one has not run.
- Store each evaluation run's dataset revision, extraction/model configuration, timestamp, raw predictions, abstentions, numerator/denominator, failure cases, and notes.
- Send the latest genuine run as `EvaluationScorecard` with `synthetic: true`, `metrics[]` and optional `baseline_metrics[]`.
- Core measures: rule field exact match, correct amendment target, effective-rule accuracy, applicant decision status accuracy, decision-flip accuracy, and blocked-invalid-source recall. State whether metrics are per-rule, per-pair, or per-applicant; show sample counts.

## 8. Contract change policy and test gates

- Pydantic is authoritative. Do not change API fields in a React component without updating `backend/schemas.py` and this file.
- Keep version `1.0.0` until implementation begins; for breaking changes use a coordinated version bump and regenerate frontend types.
- Validate models with Pydantic 2, use TypeScript generated from actual OpenAPI, and add backend/frontend contract fixtures.
- Add negative tests: no evidence; quote mismatch; reversed PDF bounds; reference mismatch; new rule unsupported; ambiguous date; stale revision; unreviewed amendment; forged-looking but *unproven* source; numeric/date mismatch in Hindi TTS; duplicate event replay.
- All features initially listed here are **design contracts**. Tests of Windows 3.12, all Sarvam endpoints, PDF boxes, and live monitoring have **not yet been performed** in this starter.
