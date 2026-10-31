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
