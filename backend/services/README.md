# Phase 1 engine boundary

All services here are pure Python and return fresh models. They have no clock,
network, database, watcher, API key or implicit approval. HTTP endpoints remain
unimplemented. Existing `backend/schemas.py` DTOs and contract version 1.0.0 are
unchanged.

## Calling the engine

- `evaluate_applicant(profile, rules, scheme_id=..., as_of_date=...,
  verified_rule_hashes=...)` produces `ApplicantDecision`.
- `plan_amendment(rules, changes, scheme_id=..., verified_rule_hashes=...,
  verified_change_hashes=...)` returns an **uncommitted** `AmendmentPlan`.
- `preview_impact(profiles, before_rules, after_rules, ...)` compares the same
  cohort and date and returns a real `ImpactEvent` with kind **PREVIEW**.

**Trust boundary:** hashes must be supplied by a trusted upstream service after
evidence, values, dates, scope and lineage have been checked. They are not source
verification themselves. `rule_fingerprint` and `change_fingerprint` bind the
entire validated payload; any content edit invalidates the supplied attestation.
Empty rule attestations yield UNKNOWN checks. Unverified change/target/proposal
inputs are rejected by the planner. These arguments must never be exposed as
client-controlled trust flags by the future HTTP API.

The planner performs rule-window/target chronology only. Publication chronology,
original-document relationships, scheme authority, immutable extraction lookup,
human review and revision/transaction enforcement are Phase 2 responsibilities.
No function here writes active rules, stored decisions or alerts, or claims that
an amendment was applied.

## Decisions and history

**VERIFIED by tests:**

- Five closed rule types; no LLM decision path. Thresholds and deadlines are
  inclusive. Age bounds are inclusive and calculated at the rule's `age_as_of`.
- Effective ranges include the start and exclude the end. No applicable rules
  yields UNKNOWN. Aggregate precedence is CONFLICT, FAIL, UNKNOWN, PASS.
- Missing document codes yield FAIL only when the inventory is complete;
  otherwise UNKNOWN. If all required codes are present, the check can PASS.
- Every relevant rule retains its check and evidence, including unverified and
  conflicting rules. Multiple verified, applicable same-type rules produce
  CONFLICT, including equal values; a target must be resolved explicitly.
- REPLACE/REVOKE close just the target interval; unrelated history is preserved.
  Proposed rules need fresh IDs. Whole-batch errors leave input models untouched.
- All 16 overall-status transitions are tested. Same status means UNCHANGED;
  only FAIL to PASS is IMPROVED and only PASS to FAIL is WORSENED.
- Hashes and output ordering are deterministic. Snapshot hashes include active
  scheme rules and their supplied verification state, so trust changes cannot
  reuse a stale decision hash. Hashes are not authenticity certificates.

**ASSUMED implementation policies, requiring explicit future extension:**

- `all_applicants` is always applicable; other scope keys match exact profile
  tokens. Tokens are not declared mutually exclusive. The planner conservatively
  rejects same-type temporal overlaps even across different scope tokens.
- Completed-years age advances on March 1 for February 29 births in non-leap
  years. This is a declared demo convention, not a legal interpretation.
- A birth date after the age anchor yields UNKNOWN with a diagnostic.
- A replacement must stay within a target's already established end boundary.
  Replacing/revoking at its start removes the zero-duration predecessor from the
  planned history; the future amendment audit log must retain that operation.
- Baseline and amended profiles are compared on one identical date, independently
  of the caller-supplied, timezone-aware preview timestamp.

**UNTESTED:** actual PDFs/OCR, production source gate, approval UI, atomic writes,
timeline `known_at`, live monitoring, Sarvam, frontend and production replay.

## Local verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.synthetic_demo
.\.venv\Scripts\python.exe -m backend.schemas
```

The synthetic demo has a strict fixture-only parser. It does not accept arbitrary
notices and does not issue source authenticity or scholarship approval claims.
