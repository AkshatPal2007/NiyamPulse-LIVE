# NiyamPulse — current progress

Updated 31 October 2026 (IST), native Windows / Python 3.12.10. Detailed evidence: [final development report](docs/FINAL_DEVELOPMENT_REPORT.md). Historical milestones are in docs/history.

## DONE — core migration and real accounts

- Existing v1 deterministic engine, five closed rule types, evidence/source lineage and v1 APIs retained. V2 multi-exam catalog, per-cycle/topic subscriptions, source intake/review and transactional deduplicated in-app delivery operate on real accounts.
- Verified-email/Argon2id/session authentication, CSRF/origin guards, ownership, throttles, deletion and server-only administrator provisioning implemented. SMTP TLS/authentication was checked earlier; owner confirmed administrator/review access. No new invitation sent.
- Active store remains var/production/niyampulse.sqlite3. Last observed: 13 genuine notices, one approved UPSC update, one verified administrator. No synthetic runtime identities or notices were introduced.
- Three exercised adapters: NTA JEE Main, NTA NEET UG and UPSC active examinations. Other catalog coverage is explicitly limited/disabled until verified. Every new publication retains human review; LLMs never decide eligibility or recipients.

## DONE — final feature and UI increment

- Editorial responsive frontend with genuine reviewed bulletin, exam directory, account views and separate administrator/user workspaces.
- Explicit optional adult-own profile inputs, topic editing, account-menu loading fix, historical before/after rule checks and distinct PASS/FAIL/UNKNOWN/CONFLICT rendering. General news does not become PASS.
- Authenticated immutable PDF/page preview and highlights only for exact native-text quote matches. HTML/OCR/unmatched sources do not get invented coordinates.
- Bounded Saaras v4 voice search and Bulbul v4 Flash reviewed-notice narration/admin preview. Both genuinely live-tested; no user recording persisted, no account actions from speech.
- Persisted declared-synthetic text evaluation and real admin scorecard. Owner confirmed profile/settings/evaluation UI works. Public support email configured with the owner's authorization.
- Full native tests: **209 passed + 38 subtests**, 78.97 s. Final focused bridge/feature regression: **37 passed**, 6.89 s. Schema/types, pip check, final frontend build and seven source hash checks pass. Production npm audit: **0 vulnerabilities**. One existing TestClient deprecation warning; three previously tracked moderate build-only advisories remain.
- Persisted benchmark: three text cases / 13 supplied profiles, **13/13** transitions and count/replay agreement. Broader accuracy and comparative baselines are not claimed.
- Desktop/390px browser checks passed: menu/search/sign-in/contact, no horizontal overflow. Screenshots: output/screenshots/final-premium-home.png and final-premium-mobile.png. Private settings/evaluation acceptance confirmed by owner.

## DONE — protected spending and native operations

- User removed INR 50 cap while retaining 500-credit floor. All earlier ledger rows preserved. Last supplied balance **596.96** before two bounded speech checks; subsequent observed ledger **14 calls / 7000 paise conservative reservations**. Estimated remaining 586.96 after holds, not verified billing balance. Snapshots expire after 15 minutes.
- Earlier real 105B extraction + Vision OCR succeeded. New Bulbul WAV (2,886,830 bytes) and Saaras transcript (179 characters, hi-IN) succeeded; no new approval/fan-out occurred. Pronunciation fidelity is not independently verified.
- Portable PORT-aware launcher, liveness/readiness, production configuration/storage guards, singleton worker lock, pinned requirements, release build and tested backup/fresh-path restore implemented. Prior recovery drill preserved real notices/admin/ledger and revoked restored sessions. Never restore over the live database.
- Owner reports baseline CI green. This increment needs a new commit/push/rerun; no push, hosting registration, paid cloud plan or public deployment was performed.

## PARTIAL — manual release acceptance

- Restart normal backend to load the new Python routes; `python -m backend.serve` after stopping the old process. QA server used only port 8001 with no second monitor worker.
- Real learner subscribe/topic/inbox/read acceptance, actual microphone/device and narration review, chosen HTTPS/tunnel deployment, SMTP link delivery, monitoring while browser closed, restart durability and backup policy remain manual release steps.
- Follow docs/DEPLOYMENT.md and docs/PRODUCTION_SETUP.md. Owner will deploy; local checks do not prove hosted production readiness. Current SQLite/worker backend needs persistent storage; Vercel Functions/ephemeral free cloud disks cannot host it unchanged.

## PARTIAL / NOT STARTED — broader future scope

- Independent gold review and expanded OCR/classification/matching benchmarks/baselines; more verified cycle-specific sources; measured capacity/security review; consent-reviewed direct child accounts. See docs/FUTURE_PLAN.md.
- Public contact is set; finalize actual retention and adult/guardian policy before public release. No legal/security certification claimed.
- Track the upstream build-only dependency fixes. The ignored untracked check.py credential must be rotated privately; its value is not recorded here.

## Reproducible checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m scripts.verify_captures
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
.\.venv\Scripts\python.exe -m scripts.build_release
npm --prefix frontend audit --omit=dev --audit-level=moderate
```

## Follow-time exam brief and Hindi/Hinglish notice queries — 31 October

Implemented authenticated GET `/api/v2/me/notice-search?q=...&cycle_id=...`.
Queries deterministically filter reviewed official updates by recognized exam,
explicit year/session and registration/schedule/admit-card/results topic. No LLM
answers or guessed dates. Unrecognized/no verified matches returns an empty result.
The existing Saaras transcript feeds this search after the user's confirmation;
typed questions use the same route. No new paid speech call was made this increment.
Following now opens My exams with a brief of existing reviewed notices, original
quoted dates/source links, independent of the selected alert topics. The first
notice opens by default; registration/schedule notices are prioritized. Dates can
be past/superseded and are labeled accordingly. Existing informational inbox
backfill no longer expires after 30 days (latest 20, idempotent and topic-filtered);
historical rule notices do not manufacture retroactive personalized outcomes.
Microphone errors distinguish insecure origin/missing device/access failure and
provide browser/Windows permission guidance. Actual device permissions require
manual verification. Production evidence/accounts/ledger remain untouched.

Verification for this increment: `python -m pytest -q tests/test_notice_search.py tests/test_auth.py tests/test_finish_features.py`: **32 passed**, 17.62 s; includes a late follower receiving a 60-day-old reviewed notice exactly once, Hindi/Hinglish session/year/topic filtering and wrong-exam exclusions. Schema export/API types, final TypeScript/Vite build and `git diff --check` pass. One pre-existing TestClient deprecation warning. No new live Sarvam call, new notice approval, production-data mutation or browser microphone acceptance was performed. Restart the backend and manually check microphone permissions/device plus the new followed-cycle brief.

## DONE / PARTIAL — judging preparation, 31 October 2026

DONE: owner restarted the stale port-8000 backend; source-preview and notice-query routes now return expected anonymous 401 instead of 404. Owner confirmed real learner follow/brief/inbox/read and captured PDF preview. Full regression: **219 passed + 38 subtests**, 51.24 s; one existing TestClient warning. Final frontend build/schema/pip checks pass; seven capture hashes verified; local preflight READY. CLI source scheduling/locking conflicts now return DEFERRED cleanly; preview missing-route guidance identifies stale backend. Existing browser-speech implementation preserved as an explicitly opt-in mode; Saaras is default and privacy copy identifies the optional browser provider.

DONE: all three official sources successfully polled at 08:32 UTC (14:02 IST); no new notices. A backup was made before publishing the validated JEE registration update after the owner explicitly verified dates against the official PDF. Now 13 discovered notices, 2 approved updates, 2 real accounts, 8 subscriptions and 2 persisted notifications at snapshot. Other guard/rule/OCR-blocked notices were retained, not bulk-approved. Review packet is under ignored var/qa. Judge guide and complete scoped feature inventory: docs/JUDGING_DEMO.md.

DONE: actual JEE administrator-preview Bulbul audio generated/cached. Selected NEET OCR and extraction lookups reused cache; its rejected extraction remained blocked. Active background processing also used the shared guarded ledger. Observed ledger after preparation: 26 operations / 13000 paise conservative reservations; last supplied balance 595, estimated remaining 545 after holds, not an actual wallet/billed reading. 500 floor and 15-minute expiry preserved; no further paid call is needed for this preparation.

DONE: owner subsequently confirmed voice search and narration work on the real device. Wider live-source coverage, independent broad gold evaluation and hosted/operational/legal acceptance remain outside this local judging pass. No new credentials, fabricated accounts/counters, cloud deployment or Git push occurred.

## PARTIAL — deployed administrator diagnosis, 31 October 2026

Read-only local check confirmed the owner's exact normalized email is a verified,
non-synthetic ADMIN in var/production/niyampulse.sqlite3. No password, session or
role was changed locally. Owner reports a paid Render deployment with persistent
storage; its remote database/session have not been inspected or modified here.
Documented the existing trusted promotion CLI and disk-path checks for the running
Render service in docs/PRODUCTION_SETUP.md. Hosted promotion requires running that
command against the actual deployed database and signing in again; no client-side
role override or automatic email-based administrator grant was introduced.

## DONE / PARTIAL — workspace layout repair, 31 October 2026

Implemented the screenshot-specific UI repair in App.tsx, VoiceTools.tsx,
ExamBrief.tsx and premium.css: correct actual sidebar navigation selectors/contrast,
synchronized sidebar/main widths, shrinkable voice grid columns and wrapped text,
full-width labeled notice query, compact question/settings layout, readable notice
cards with literal source excerpts collapsed by default. Preserved all voice/provider
choices, real-data fetching, official links and unmodified literal evidence.
No backend/schema/role/data/budget changes. Frontend TypeScript/Vite build passes;
owner selected “I’ll check it myself” for authenticated visual acceptance. The local preview is open; no private UI screenshot or desktop/mobile browser pass is claimed for this increment. Existing backend was left running; no deployment or Git push performed.
