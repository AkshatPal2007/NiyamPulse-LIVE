> Current status: see [FINAL_DEVELOPMENT_REPORT.md](FINAL_DEVELOPMENT_REPORT.md) and [PROGRESS.md](../PROGRESS.md). The phase descriptions below define scope; their original future-tense wording does not override the current status list. No hosted deployment was performed.

# Future implementation plan — NiyamPulse

Updated after implementation and native verification on 31 October 2026.
The original audit is historical; current evidence is in
[PHASES_1_3_REPORT.md](history/PHASES_1_3_REPORT.md).

- Phase 1: **complete for the explicit closed-rule subset**.
- Phase 2: **complete**; user-reviewed genuine UPSC alert persisted and read.
- Phase 3: **implemented/tested within declared bounds**; three real adapters,
  rotating intake, observed attachments, durable queue and credit protection.
- Phase 4: implemented: optional adult-own profile inputs, per-rule checks and honest four-state rendering.
- Phase 5: real accounts and native deployment preparation implemented; hosted acceptance remains manual.
- Phase 6: PARTIAL. Persisted three-case/13-profile synthetic text benchmark and replay agreement work. Independent gold review, broader OCR/classification/matching measurements and comparative baselines are still required.
- Phase 7: bounded Saaras v4 / Bulbul v4 Flash integrated and live-tested with reviewed public notice text/generated audio. Real microphone/device and pronunciation acceptance remain manual.
- Release UI: editorial redesign implemented; desktop/phone browser checks and owner confirmation of settings/evaluation succeeded.
- Spending: INR cap removed by the owner; preserve the 500-credit floor, every ledger row and 15-minute manual balance expiry. Last supplied balance 596.96; two speech checks consumed conservative reservations, not a verified billing amount.
- CI: owner reports both jobs green before this increment. Push/rerun the new changes; no new remote run was performed by the agent.

The detailed phase requirements below remain the implementation/acceptance
reference; completed items are documented in the phase report.

## Product goal

A dependable multi-exam notification platform: students follow exam cycles;
configured official sources are monitored automatically; each new/changed notice
is processed once with evidence; a human operator reviews it; relevant subscribers
receive source-linked English/Hindi in-app alerts. Optional personal impact uses
only the verified closed-set Python engine and opted-in data. It never constitutes
official eligibility or application confirmation.

Keep the existing repository, deterministic evaluator, evidence and useful UI. No restart,
nationwide-coverage claim, new paid provider, public deployment or removal of old
working code is part of this plan without the relevant authorization.

## Phase 1 — Stabilize the rule bridge (highest priority)

**Implement:**

- Turn the audit counterexamples into failing regression tests first.
- Reject negations/exemptions, ambiguous categories/scopes, optional document
  alternatives, uncertain dates and unspecified effective/age-anchor dates.
- Preserve document identities; passport must never become Aadhaar. Use exact
  integer/Decimal monetary conversion. Derive stable IDs from verified inputs.
- Require independently verified candidate values/scope/source lineage before
  supplying trusted hashes. Do not auto-attest every model-generated proposal.
- Resolve explicit amendment targets and scheme/cycle lineage; reject ambiguous
  matches and mixed supported/unsupported changes as a whole.
- Persist closed/revoked intervals and immutable history/version records correctly.
  In-memory and reloaded decisions/hashes must agree before and after restart.
- Add optimistic cycle rule-set revision checks, atomic rollback, stale-analysis
  revalidation and India calendar semantics. Do not use UTC date/today as a source
  fact or imply arbitrary exam eligibility is supported.
- Update SHARED_CONTRACTS and schemas together, including notice_changes and any
  proposed-rule review DTO/version change.

**Your manual input:** only when an actual source clause's meaning, effective
scope/date or amendment target is ambiguous; confirm it from the source or keep
it held. No new service/account is needed for isolated regression work.

**Exit:** the demonstrated failures abstain correctly; ADD/REPLACE/REVOKE chains,
source failures and concurrent stale writes have passing negative tests; persisted
history exactly reproduces planned decisions. Until then, personal-rule
publication stays a partial feature, even if happy-path tests pass.

## Phase 2 — Finish one genuine informational-notice acceptance run

**Implement:** separate informational mentions of eligibility from actual rule
amendments, fix NTA's false-positive hold without weakening evidence checks, and
revalidate its cached source passages. Make pending, extraction-valid, held,
reviewed and published states unmistakably different. Preserve existing alerts.
Check a complete original/corrigendum or informational-source workflow through
the actual parser, gate, review, match and notification path.

**Your manual input:** inspect the genuine UPSC ESE 2027 notice and original source,
enter your own reason and approve/reject. The Engineering learner is already
subscribed with Hindi selected. Leave NTA held until its operative-rule issue is
resolved; do not bypass the guard simply to complete a demo. Historical notice
dates do not mean applications are currently open.

**Exit:** a reviewed real-source notice delivers exactly once to matching synthetic
subscribers, excludes unrelated/paused subscribers, preserves quoted evidence and
language, records READ, and produces matching database-derived admin totals.

## Phase 3 — Make monitoring and processing dependable, then expand sources

**Implement:** rotate/paginate beyond the five-document poll cap; detect changes
inside relevant attachments; isolate per-source failures; add scheduler recovery
and truthful freshness/heartbeat indicators. Add a durable processing queue with
idempotent OCR/105B jobs, bounded retries, explicit credit exhaustion and cache
labels. Human approval remains mandatory; notification delivery is still in-app.

Add one additional publisher/adapter at a time (for example the configured NEET
or SSC candidate), including exact year/session mapping and real source checks.
Do not advertise a catalog item as monitored before its adapter proves extraction.

**Your manual input:** clarify publisher/year/scope when sources are ambiguous or
require interactive access. Approve any larger API budget before increasing the
current cap; INR 50 is reserved of INR 50, not a provider bill. No CAPTCHA bypass.

**Exit:** new and changed links are eventually processed, transient failures do not
stop other sources, queued jobs survive restart, and every additional enabled
adapter has actual observed evidence plus offline fixtures.

## Phase 4 — Complete personal-profile and impact UI

**Implement:** opt-in fields for supported data, honest missing-data behavior,
review of proposed rules/targets and before/after checks/evidence. Render actual
PASS/FAIL/UNKNOWN/CONFLICT distinctly and preserve unsupported-case abstention.
Correct the current unconditional 'No eligibility assessment was made' copy when
an evaluation really occurred. Reflect validated rule approval in UI controls.

Keep general exam news available without personal details. Animate only actual
backend state changes; same overall status is unchanged. Provide accessible
Hindi/English explanations with protected numbers/dates and visible disclaimer.

**Your manual input:** validate the desired profile fields and example scenarios
using synthetic applicants; do not bring real student PII into tests/screenshots.

**Exit:** a person can use the feature through the UI, with privacy deletion,
correct complete/missing/conflicting outcomes and no inferred official approval.

## Phase 5 — Real accounts and deployment preparation

**Implement:** production identity/session handling and account ownership,
operator-role provisioning, secure configuration, backup/restore, migration
verification, audit logging and appropriate privacy/consent controls. Synthetic fixture identities are restricted to isolated tests. Verify migration 004 against a
backup of the existing SQLite database before bridge rollout.

**Your manual input:** choose the authentication approach/provider and target
hosting environment; create/manage accounts, domain and credentials locally.
Confirm costs and public deployment scope before an external service is added.
No new provider is required for the current localhost prototype.

**Exit:** ownership/security tests, tested upgrades/restores and appropriate user
consent flows work; the operator role cannot be selected by an arbitrary visitor.
Do not publish the current demo login as production authentication.

## Phase 6 — Measured evaluation and a reproducible demonstration

**Implement:** declared synthetic gold corpus covering information, amendments,
scanned/Indic text, wrong cycles, forged-lineage/suspicious inputs, missing fields,
conflicts and duplicates. Persist evaluation runs and baseline versions; only then
show a scorecard. Measure source/classification/extraction/matching correctness,
unsupported-rule abstention, replay determinism and actual latency.

Prepare the 90-second source discovery → review → relevant learner inbox demo.
Offline replay uses the same evaluator/notification path and is clearly labeled.

**Your manual input:** review gold labels and the intended demo sequence. Resolve
ambiguous gold cases through source review rather than guessed expected answers.

**Exit:** reproducible reports and replay produce traceable outcomes; every UI
metric comes from a recorded run, and a clean Windows setup can reproduce the demo.

## Phase 7 — Optional voice after the core flow is reliable

Add Saaras/Bulbul only if useful to the final experience. Verify supported models
when implementing; use the existing Sarvam account if available. Validate all
named rules, values, dates and statuses before speech, and block audio on guard
failure. Provide transcripts and text fallback.

**Your manual input:** choose voice scope/languages, approve the test budget and
supply non-sensitive test audio/microphone consent when needed.

**Exit:** real measured calls work, unsafe generated content never reaches TTS,
and accessibility benefits are demonstrated. Voice is not a prerequisite for
reliable exam subscriptions and notices.

## Working method for every phase

1. Preserve active code/data; record VERIFIED, ASSUMED and UNTESTED separately.
2. Reproduce the defect or add a meaningful failing test, then implement a small
   increment and run relevant native Windows checks.
3. Update PROGRESS, contracts and the current handoff with observed results.
4. Keep review/approval and any new account/cost decisions as explicit human gates.
5. Do not confuse code present, tests passing, a migrated database, a working UI
   and a verified real-data run; each needs separate evidence.
