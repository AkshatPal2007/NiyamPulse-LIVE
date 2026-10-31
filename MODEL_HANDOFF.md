# NiyamPulse — current engineering handoff

Read AGENTS.md, SHARED_CONTRACTS.md, PROGRESS.md and docs/PRODUCTION_SETUP.md.
Continue this repository; preserve the deterministic five-rule engine, immutable
source lineage, explicit human publication review and 500-credit reserve.

The runtime is now a real-account application, not a persona demo. React has a
public landing/catalog/reviewed feed, email-link account setup, password sign-in/
recovery, account settings and role-protected admin views. Auth uses Argon2id,
hashed action tokens, HttpOnly cookies, CSRF/origin guards, HTTPS production mode,
throttles and server-only administrator assignment. No bearer token in browser
storage and no UI role selector. Tests can explicitly opt into retained fixtures;
environment variables cannot enable demo identities.

Active data: var/production/niyampulse.sqlite3; .env selects it. It contains genuine
web evidence and the human-approved UPSC update, with no demo users/subscriptions/
notifications. The source archive remains backed up. Never reset the new store or
create placeholder real users. Historical reviewer IDs are audit records, not
active credentials. Real users must own and verify their mailbox.

SMTP is configured privately and TLS/authentication succeeded. The owner already
had a verified account; trusted-console promotion granted ADMIN after ownership/
adult confirmation. The user confirmed real admin dashboard/review queue access.
No invitation was sent in this task. Do not request passwords or mail secrets in chat.

Deployment preparation is implemented: backend.serve, operations preflight/SMTP
check/online backup/fresh-path restore, runtime lock, typed health endpoints,
production storage/configuration guards, exact runtime dependency lock, CI and
review-only Render example. Read docs/DEPLOYMENT.md. Native full suite: 199 passed
+ 38 subtests; schema/types/pip checks and final frontend build pass. A real local
backup/restore drill preserved notices, admin and all financial reservations;
restore revokes sessions/actions. Do not restore over or reset the live database.

User plans to deploy manually, considering free Vercel/Render. Current local
SQLite + long-running workers + SMTP require stateful persistent hosting. Render
Free/Vercel Functions are unsuitable. A free external DB/storage/mail/scheduler
migration is future work; no provider, cost, Linux/hosted success or public URL is
claimed. Example Render paid plan/disk are drafts only. Real hosted learner/email/
restart acceptance and privacy/operational readiness remain manual release steps.

Production npm dependency audit has zero findings. Full npm audit has three
moderate build-tool findings through minimatch/Redocly/openapi-typescript; pinned
7.13.0 only reads our trusted generated local schema and is not bundled at runtime.
Track the upstream fix. Native Windows Python 3.12.10 verified; Linux CI is prepared,
not observed. Do not claim a completed security audit or verified child consent.

Fake identities/mail exist only in isolated tests. No new paid Sarvam calls:
10 admitted operations / 5000 paise reserved, full original cap. Paid processing
remains paused. Cached extraction and free official-source polling still work.

NTA JEE, NTA NEET and UPSC were freshly polled; thirteen genuine notices remain,
one reviewed update is public. Source defaults for fresh installs stay disabled
until independently tested. No new unreviewed notice is auto-published.

Old milestone docs are under docs/history; v1 docs/tests remain. Cleanup archived
old screenshots and removed generated caches. User changes and all real source
bytes/caches were preserved. No Git push or cloud deployment occurred. Agent QA
uses its own port 8001 without a second worker and is stopped at final teardown.
