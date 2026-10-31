# Phases 1–3 implementation report — 31 October 2026 (IST)

## Result

**Phase 1: complete for the deliberately narrow closed-rule subset.**
**Phase 2: complete, including actual human acceptance.**
**Phase 3: implemented and tested within the limits below.**

This continues the existing v2 project and preserves v1 code, schema 1.1.0,
fixtures and deterministic evaluator. It does not claim general exam eligibility,
production authentication, nationwide monitoring, voice output or benchmark accuracy.

## VERIFIED — rule safety and persistence

- Reproduced audit failures before fixing them. Negations/exemptions, missing
  scope/dates/age anchors, guessed targets and mixed unsupported batches abstain.
- The parser accepts only explicit literal Published/Effective/Scheme/Operation/
  Target/Scope context plus the existing closed EN/HI clause grammar. Monetary
  values use integer INR; units such as free-form lakh phrases are held rather
  than converted with floats. Document codes are preserved, including PASSPORT.
- Stable identifiers bind cycle, source content hash, extraction version and quote.
- Publication rechecks immutable bytes, exact page spans and publisher ancestry,
  recomputes typed proposals, checks acquisition/publication chronology in the
  India calendar, and only then provides explicit hashes to the unchanged v1 planner.
- No self-attestation in apply_rule_bridge. Missing attestations and tampered
  values/rule flags fail closed. Stale cycle revisions roll back the whole review,
  rule history, updates, matches and notifications transaction.
- Migration 005 appends complete immutable history snapshots and revision/hash
  heads. ADD → REPLACE → REVOKE round-trips reproduce rules, hashes and decisions
  after reload, retaining shortened historic intervals. Draft migration-004-only
  rule data requires review; existing runtime had no such rows.
- A SQLite backup was retained at var/backups/before-future-phases-1-3.sqlite3
  before applying the additive runtime migrations.

## VERIFIED — genuine notice acceptance

- Removed specific informational false positives from the JEE notice. Generic
  or operative eligibility/qualification language still requires rule review.
- Literal resolution permits unique whitespace alignment and a closed list of
  announcement label/newline separators. Values, operators and other punctuation
  cannot be normalized. Returned anchors always quote frozen source text exactly.
  Guard version: explicit-rules-label-anchor-v7; raw cached provider results reused.
- NTA JEE Main 2027 Session 1 and UPSC ESE 2027 both revalidate without a new charge.
- The user personally reviewed and approved the genuine UPSC metadata notice,
  then opened and read the matching Engineering learner alert. The user confirmed
  “yes done it works”; persisted data independently verifies:
  - notice-a5e21cc4de994253891feac3f844fb82: APPROVED, revision 6;
  - exactly one associated update and one real-source publication overall;
  - notification-bdc3a1dea3954e45b443b10ca22cb383: demo-engineering, English, READ;
  - approved at 2026-10-30T21:36:54.360379Z; read at 21:37:11.617688Z.
- That learner's current English preference and the user's additional subscriptions
  were preserved. Controlled Hindi source summaries remain available; the isolated
  captured-UPSC acceptance test also verifies Hindi matching, deduplication and reads.
- Existing saved alerts remain readable under the previous disclaimer literal;
  new responses use “Decision support only; not official approval.”

## VERIFIED — real sources, queue and UI

- Three individually exercised adapters: NTA JEE Main, UPSC active exams, NTA NEET
  UG. First two are different publishers. NEET is another adapter from NTA.
- Captured NEET's public listing and robots policy using actual HTTPS on native
  Windows. Listing SHA-256:
  5191b1000915664386278fb67ee9e23e79a24e429b801a15971261e3443c51c8.
  It yielded 11 recognized links: 10 exact 2026 mappings and one unmapped item
  without an explicit year. Identifying topper-list titles are excluded.
- Added NEET UG 2026 as explicitly post-exam notices, distinct from NEET UG 2027.
  Source checked/enabled only after actual usable mapped extraction. Scans are
  retained and queued separately; they do not count as parsed/approved notices.
- Listings rotate in batches of five, so the actual second NEET batch reached
  another five notices. Year/session ambiguity stays unmapped.
- UPSC PDF attachments rotate separately, with immutable listing → exam-detail →
  PDF ancestry verified again at publication. The actual ESE attachment contains
  62 pages / 1,615,355 bytes and is retained with complete bounded embedded text.
  V2 limits: 100 PDF pages, 2 MiB text, 10 MiB HTTP. V1 retains its 20-page limit.
- Durable processing jobs persist idempotently, use exclusive five-minute leases
  and ownership tokens, isolate failures, cap retries at three, and pause uncertain
  paid submissions/lost leases. They never approve or send alerts. Human review
  completes the queue row atomically; startup also reconciles older terminal rows.
- A genuine long-text notice exposed a pre-existing trailing-newline offset bug.
  New excerpts now trim before computing offsets. Legacy repair is allowed only
  before analysis/review, preserves the same literal quote/source bytes, and reruns
  the full provenance check. Changes beyond whitespace are refused.
- Source scheduler failures are isolated per source and retried; heartbeat freshness
  controls coverage claims. UI shows recorded source checks, OCR backlog, job states,
  actual pauses, credit reserve and source-backed rule proposals. Personal alert
  wording now reflects returned before/after statuses.
- Browser QA verified the operator data, budget/queue panel, genuine UPSC review
  screen and saved-alert compatibility. Local proof images are under output/screenshots.

## VERIFIED — cost controls and actual Sarvam outcomes

- User refreshed the dashboard and reported **598.12 credits** during this task.
  Enforced fixed **500-credit floor** alongside the prior **₹50 total local cap**.
- There is no live balance API integrated. The dashboard observation is manual,
  bound to the API-key fingerprint, expires after 15 minutes, and deducts all new
  conservative ₹5 reservations. Missing/stale/low snapshots block paid admission.
- Before this task: 7 admitted operations / ₹35 reserved. This task admitted three
  additional operations / ₹15 reserved: one 105B response rejected for nonexistent
  page references; one real Vision recovery completed for a one-page NEET scan;
  one 105B extraction of that recovered notice validated literal facts but proposed
  an unsupported legal warning, so it remains held. No success was fabricated.
- Now: **10 admitted operations, ₹50 reserved; paid requests paused.** Conservative
  remaining estimate from the snapshot is **583.12 credits**, not a provider bill
  or a newly queried balance. Other organisation keys/products share the balance.
- Revalidation, source capture, repairs, queue reconciliation and human publication
  added no further paid operations. No model/provider change or budget increase.

## Validation

Native Windows, Python 3.12.10:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
npm --prefix frontend run build
```

Full suite: **173 passed, 38 subtests passed**. One existing Starlette/httpx
TestClient deprecation warning. Schema smoke, dependency check, regenerated types
and TypeScript/Vite production build pass. Vite's native esbuild spawn needs the
approved local sandbox exception on this machine; ordinary restricted spawn fails
EPERM. Native code tests require no new paid calls.

New regressions cover semantic abstention, all five explicit rule clauses,
attestation absence, history round-trip, stale publication and rollback, future
publication chronology, informational intent, literal punctuation, credit limits,
old-alert compatibility, captured UPSC informational fanout/read/dedup, source
rotation, exact NEET routing, scheduler isolation, leases/restart, queue admission,
long PDFs, attachment ancestry and whitespace-only legacy excerpt repair.

## Limits / next work

- Arbitrary natural-language exam eligibility remains unsupported. Conservative
  holds are intentional; human review alone cannot turn unsupported rules operative.
- Current remaining extraction backlog is paused at the budget cap. Monitoring
  and cache processing continue without paid calls; do not raise the cap silently.
- Source defaults are disabled on a fresh installation until actual verification.
  Existing local runtime has three enabled adapters; SSC/GATE remain disabled.
- Account personas are synthetic. No actual applicant PII was introduced.
- Run one monitor stack: the API's workers or backend.monitor, not both. Long polls
  may conservatively age heartbeat freshness; do not interpret this as proof that
  a blocked source or stalled worker is healthy.
- The user restarted port 8000 for acceptance. A Python process retains imported
  code: the final queue-completion/excerpt-offset hotfixes load on its next restart.
  Existing queue metadata was reconciled with the latest code without changing
  the user's review, read state, preferences or subscriptions. Agent QA uses port
  8001 without workers and is stopped separately; the user server is untouched.
- Next product phase is 4: opt-in profile and impact UI, followed by measured
  multilingual evaluation, production identity/operations and demo hardening.
  No push, deployment, automatic real-source approval or extra paid service occurred.
