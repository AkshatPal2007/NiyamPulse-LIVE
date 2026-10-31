# NiyamPulse — current progress

Updated 31 October 2026 (IST). Verified on native Windows / Python 3.12.10.

## DONE — real product and accounts

- React public home, exam search/cycle selection, reviewed source feed, personal
  subscriptions/inbox, preferences, account deletion and separate admin workspace.
- Verified-email signup, Argon2id passwords, password recovery, expiring/revocable
  HttpOnly sessions, CSRF/origin checks, bounded API bodies and persisted throttles.
- SMTP app credential supplied privately; TLS and authentication succeeded against
  the configured provider. SMTP-check sent no message and printed no secrets.
- The owner's existing verified account was promoted through the trusted CLI after
  explicit ownership/adult confirmation. The user signed in again and confirmed
  administrator dashboard and review queue access. No new invitation was sent.
- Public signup cannot set roles; no persona switch or synthetic runtime accounts.
  Registration is for adult holders/guardians by self-declaration; verified parental
  consent/direct child accounts and legal/security certification are not claimed.
- Required v2 disclaimer is visible and used by new DTO defaults. Existing v1
  evaluator, evidence handling, five supported rule types and tests remain intact.

## DONE — genuine data and protected spending

- Active store: var/production/niyampulse.sqlite3. Current observed state: 13 genuine
  discovered notices, one reviewed UPSC update, one verified real administrator.
  Historical raw evidence/extractions, review history and source configuration remain.
- Three exercised adapters: NTA JEE Main, NTA NEET UG and UPSC active examinations.
  Unsupported/new sources stay disabled until tested. Source lineage/explicit human
  review are mandatory; LLMs do not decide eligibility or notification recipients.
- Previous demo accounts/inbox data were excluded from the active store; obsolete
  milestone docs/screenshots were archived, not substituted for real records.
- Ten admitted Sarvam operations reserve 5000/5000 paise. No new paid operations
  in this SMTP/deployment work. The 500-credit guard remains; wallet balance is not
  inferred from the ledger. Paid processing stays paused; preserve this DB on deploy.

## DONE — deployment preparation, verified locally

- One-process portable launcher: python -m backend.serve; PORT-aware, asyncio/h11,
  bounded concurrency, quiet access logs and graceful shutdown settings.
- Production refuses unknown/local cloud modes, non-durable storage declarations,
  incomplete SMTP, demo flags and unsupported serverless hosting. Render requires
  a real persistent mount. API/standalone worker share an OS-owned runtime lock.
- Public typed liveness/readiness endpoints: /api/v2/health/live and /health/ready.
  Readiness reports DB/frontend/worker failure as 503 without private details.
- Production API docs are disabled; API bodies are bounded before parsing; HTML
  revalidates and hashed static assets use immutable caching.
- Pinned Python runtime dependency lock, locked npm build script, production env
  example, non-active paid Render Blueprint and Windows/Linux verification workflow.
- Online backup + SHA-256 manifest; restore refuses overwrite and revokes sessions/
  action tokens. Actual local recovery drill preserved 13 notices, one update,
  one administrator and all ten/5000-paise reservations. Live DB was not restored.
- Full manual hosting/cutover/rollback instructions: docs/DEPLOYMENT.md. No cloud
  service was registered, paid plan purchased, public site deployed or Git push made.

## VERIFIED — latest checks

- Native full suite: **199 passed, 38 subtests passed**, 65.91 seconds.
- Four initial deployment regressions were reproduced before their fixes: missing
  health endpoints, unbounded generic API bodies, invalid environment fallback and
  production API docs exposure. Recovery/locking/admin retry tests also pass.
- One existing Starlette/httpx TestClient deprecation warning.
- The actual PORT-aware launcher was started on temporary loopback port 8001;
  both health endpoints returned 200. No second monitoring worker was started.
  Final built-asset checks found no configured SMTP/Sarvam secrets.
- Schema generation, API type generation, pip check, locked npm install and final
  TypeScript/Vite build pass. Frontend production dependency audit: zero findings.
- Full frontend audit still reports three moderate build-only dependency findings
  from the minimatch advisory through Redocly/openapi-typescript. Generator 7.13.0
  remains pinned and reads only our locally generated trusted schema; it is absent
  from the shipped frontend. A compatible upstream fix remains a tracked item.
- Original desktop public UI checks and the user's real admin access confirmation
  are verified. Device viewport emulation, Linux CI and hosted acceptance are not
  claimed as completed locally.

## PARTIAL — public deployment and acceptance

- User will select/provision the host manually. Current architecture needs a
  stateful service + persistent disk, canonical HTTPS origin and private secrets.
  Render Free loses SQLite data, sleeps and blocks SMTP; Vercel Functions do not
  provide persistent local SQLite. These are unsuitable for this current backend.
- Remaining: run Linux CI, deploy chosen persistent service, privately restore the
  backup/financial ledger, check hosted SMTP/link delivery, test a real learner's
  subscribe/inbox/read flow, verify monitoring with browser closed and restart
  durability. Finalize operator privacy/contact/retention and adult/guardian policy.
- The example Render plan/disk are paid and review-only; no cost was incurred.

## NOT STARTED / future scope

- Fully free hosting architecture: durable external DB/evidence storage, HTTP mail
  transport and an independent scheduler. Do not pretend the SQLite app already
  supports these services or provision new providers without the user's direction.
- More verified exam/source adapters, consent-reviewed direct child accounts,
  stronger operational/security review and measured capacity tests.
- Optional Saaras/Bulbul voice features. Never invent a successful voice/API result.

## Reproducible commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
.\.venv\Scripts\python.exe -m scripts.build_release
npm --prefix frontend audit --omit=dev --audit-level=moderate
.\.venv\Scripts\python.exe -m backend.operations smtp-check
.\.venv\Scripts\python.exe -m backend.operations preflight
.\.venv\Scripts\python.exe -m backend.operations backup
```

Preflight currently passes in local mode; that is not proof of hosted production.
Historical milestones are archived in docs/history; current contracts and this
progress file take precedence over their old pending/completed claims.
