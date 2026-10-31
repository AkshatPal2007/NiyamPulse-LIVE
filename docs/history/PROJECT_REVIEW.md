# Project review — 31 October 2026 (Asia/Kolkata)

> Historical pre-implementation audit. Its counterexamples are now covered by
> regressions and fixes; see [phases 1–3 report](PHASES_1_3_REPORT.md) for current
> verified state. Keep this record as the evidence that motivated the changes.


## Assessment

NiyamPulse v2 is a working **local informational-notification prototype**, with
preserved v1 scholarship tooling. It is not yet a production exam-eligibility
platform. The newer v2 personal-rule bridge exists in the working tree, but has
blocking correctness and acceptance gaps. A green test suite does not establish
that those untested policy/temporal cases are safe.

Scope reviewed: repository instructions/contracts/history, backend services and
DTOs, migrations, frontend flows/configuration/generated types, test modules,
synthetic fixtures, source verification notes and a read-only runtime SQLite
snapshot. Forty-eight Python source files parsed successfully. Dependencies,
credentials and arbitrary applicant data were not inspected as source code.

Git baseline: committed migration `1a9b713` (`new archi`), following `70ada56`.
New rule-bridge edits appeared during the review and were preserved. This audit
changes documentation only; it does not fix, replace, commit or deploy that work.

## VERIFIED current capabilities

| Area | Evidence-based state |
|---|---|
| Multi-exam catalog | 15 exams, 10 configured cycles; catalog membership is not live coverage |
| Subscriber flow | Cycle/topic subscriptions, pause/unfollow, owned inbox and read state implemented |
| Operator flow | Source health, review/reject/quarantine, revision checks and actual database counters |
| Source monitoring | NTA JEE Main and UPSC active-exam adapters implemented and previously exercised against actual publishers; other adapters not established |
| Evidence/storage | Immutable raw captures/extractions, hashes, exact page quotes, transactional publication/dedup |
| Sarvam | Actual authenticated 105B requests and Vision OCR; cached processing, strict DTOs and local credit-reservation cap |
| Language | Extractive English and controlled Hindi labels/value copies; unrestricted translation/audio not complete |
| V1 engine | Five rule types, four statuses, deterministic precedence/impact and source checks preserved |
| V2 rule bridge | New migration, parser, storage and backend fan-out code present; acceptance remains PARTIAL |
| Accounts | Two synthetic learners and one local operator; this is demo role selection, not public authentication |

## Runtime snapshot (read-only)

- Four subscriptions and three persisted in-app notifications/matches; current
  published notifications originate from synthetic notices.
- **Zero published real-source updates.** Both real notices remain NEEDS_REVIEW.
- UPSC ESE 2027: analysis VALIDATED, `requires_rule_validation=false`; can proceed
  to genuine human source review.
- JEE Main 2027 Session 1: newer cached analysis now VALIDATED, but
  `requires_rule_validation=true` with **zero proposed rule changes**. The current
  backend and UI still block publication. It is inaccurate to call it ready to
  publish merely because its extraction badge is validated.
- The inspected runtime database does **not** yet contain `v2_rule_sets` from
  migration 004. New source code and the running/local database are therefore
  different rollout states. Back up and verify migration before using the bridge.
- Sarvam ledger remains seven admitted operations, INR 35 reserved of INR 50.
  These are local reservations, not a provider bill. This audit made no paid calls.

## Verification run during this review

- Native Windows Python 3.12: **132 tests passed, 38 subtests passed**, 28.71 seconds.
- One existing Starlette/httpx TestClient deprecation warning; no dependency errors.
- TypeScript/Vite production build passed.
- `python -m backend.schemas`, `python -m pip check`, Python AST parsing passed.
- Earlier 101-test results describe the committed slice; the fresh 132-test result
  covers the newer working-tree bridge tests. Code remains under active development.

## Confirmed blockers the current suite misses

All probes below used isolated synthetic inputs. The persistence probe used a
fresh temporary database and left real runtime data unchanged.

### 1. Clause parsing changes the meaning of source text

In `backend/services/rule_bridge.py`, `_try_parse_marks` and
`_try_parse_required_documents` currently produce:

| Synthetic source clause | Observed result | Required behavior |
|---|---|---|
| Applicants with less than 60% marks are exempt from the minimum marks requirement. | Minimum marks >=60%, no diagnostic | Do not reverse an exemption into a threshold; abstain/review |
| Documents required: passport. | Required document DOC_AADHAAR | Preserve actual requirement/alternatives; never substitute a different document |
| Application deadline: 06/07/2027, no publication/effective metadata | Date interpreted as 2027-07-06 and used as effective start | Require established date format and explicit effective context; do not guess |

Marks/document rules also fall back to `date.today()` when source publication is
missing. Age anchors can fall back to the latest mentioned date/current date.
Those are inferred operative facts, not source verification. UUIDs and the wall
clock also make this supposedly pure conversion non-reproducible.

### 2. Planned rules and persisted rules diverge after REPLACE

A synthetic minimum-marks rule of 70%, effective 2027-01-01, was replaced by 60%
effective 2027-02-01. The planner correctly closed the old interval at February 1.
`ExamStore.persist_rule_changes` inserted the new rule but did not persist the
old rule's shortened interval. Reload left both rules open-ended.

For an applicant with 65% marks on 2027-03-01:

- In-memory planned decision: **PASS**.
- Reloaded persisted decision: **CONFLICT**.

Fix temporal persistence/history before treating a bridge publication or its
stored snapshot hash as correct. Cover REVOKE, repeat amendments and restarts too.

### 3. Verification boundary and amendment targeting need hardening

`apply_rule_bridge` promotes all supplied old/proposed rule hashes and changes
into the verified set. Presence of a model candidate and evidence anchors is not
independent numeric/date/scope/lineage verification. `_find_active_rule` picks the
first same-type rule rather than resolving one explicit scoped target. Publication
also needs a cycle rule-set revision to prevent stale analyses replacing newer
rules. `verified_analysis` rechecks summaries/quotes but does not independently
recompute/bind `notice_changes` against source semantics and the current rule set.

These are code-review findings to resolve with adversarial tests, beyond the
positive unit tests that currently pass.

### 4. UI and public contracts lag behind the backend bridge

The review button is disabled whenever `requires_rule_validation` is true, even
if changes exist. No complete personal-rule review/profile/impact UI exists.
The inbox always says no eligibility assessment was made, while the new backend
can produce personal before/after decisions. `NoticeAnalysis.notice_changes` was
added to Python/generated types without the paired public-contract documentation.
Finish the user-facing flow and contracts before calling personal impact done.

### 5. Monitoring and processing have a declared incremental scope

Only the first five mapped documents are examined each poll; there is no rotation
or cursor to ensure later links are eventually visited. UPSC attachment-level
changes are not monitored. Source discovery is automatic, but paid Sarvam
processing is currently an explicit admin action rather than a durable automatic
processing queue. A scheduler check exception can exit its worker; add per-source
failure isolation, worker-health tests and recovery before expanding coverage.

## ASSUMED / UNTESTED

- Intended deployment remains native Windows/localhost with synthetic personas.
- No public-authentication, child-consent or production hosting readiness is claimed.
- No measured accuracy scorecard, broad all-exam coverage, guarded TTS, exact PDF
  coordinate verification or completed real-source publication test is claimed.
- API connectivity and a VALIDATED extraction do not establish publisher
  authenticity, official eligibility, applications being open, or rule safety.

## Cleanup completed

Removed **13 ignored generated cache/scratch targets**, reclaiming **1,320,936
bytes** (about 1.26 MiB): Python bytecode caches, old pytest/orphaned temporary
directories, obsolete smoke log, temporary synthetic PNG renders and duplicate
HTTP probes. Probe bytes AND metadata were verified identical to the tracked
official fixtures/manifest before removal. No deletion was skipped.

Preserved `.env`, `.venv`, Node dependencies, built UI, generated API types/OpenAPI,
SQLite runtime data, source/extraction/model caches, synthetic datasets, tracked
PDFs/screenshots, legacy engine, Git history and all concurrent source edits.
No server was stopped and no additional API key/provider/payment was used.

See [FUTURE_PLAN.md](../FUTURE_PLAN.md) for the next implementation sequence.
