# NiyamPulse

**Official exam updates, clearly explained.**

A real-account exam-notification platform for Indian exam aspirants and adult
holders/guardians following school/engineering exam cycles. Browse reviewed source
notices, follow specific exam years/sessions, and receive matching in-app alerts.
NiyamPulse is independent of exam organizers; original notices remain authoritative.

## Run on native Windows

Python 3.12 and Node.js LTS. Existing dependencies/build are prepared on this machine.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-production.lock.txt -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m backend.serve
```

Open http://127.0.0.1:8000/. Public catalog/reviewed updates need no sign-in.
There is no persona switch, default password or automatically seeded account.

For real registration and administrator access, follow
[production/account setup](docs/PRODUCTION_SETUP.md). Configure SMTP privately,
run `python -m backend.accounts invite-admin`, then open the emailed single-use
link to choose a password. Registration/recovery remain explicitly unavailable
until mail is configured. Keep passwords/API keys in ignored `.env`, not in chat.

`NIYAMPULSE_ENV=production` requires a canonical HTTPS `NIYAMPULSE_PUBLIC_URL`
and enables Secure host-only cookies. Production also requires an explicit absolute
data path, verified durable storage declaration and complete SMTP. The provided native loopback configuration
is for local operation; hosting/domain/TLS are not provisioned by this repository.

## Real data and source review

The active SQLite store is `var/production/niyampulse.sqlite3`. A backed-up one-way
cutover preserves genuine evidence and approved history while excluding demo
accounts, subscriptions, inbox rows, notices and fixture workspaces. The original
database is an archive. Current data: 13 genuine discoveries and one human-reviewed
UPSC update and one verified real administrator; no fabricated production users.

Three exercised adapters cover NTA JEE Main, NTA NEET UG and UPSC active exams.
Polling rotates through links and observed attachments. Exact years/sessions are
required; catalog presence does not mean active monitoring or open registration.
New/changed notices wait for a human operator's review before publication/alerts.

Sarvam only extracts/explains. The retained pure Python evaluator alone handles
five supported rule types; arbitrary exam eligibility remains unsupported.
The original ₹50 local reservation cap is fully used; further paid processing is
paused, with a 500-credit reserve protected. Cached work and free monitoring
continue. No per-subscriber model calls or official application submissions occur.

## Tests and contracts

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
npm --prefix frontend run build
```

Current native suite: **199 tests + 38 subtests pass**. Security tests use isolated
synthetic accounts/captured mail and never populate the active store. Current
[progress](PROGRESS.md), [API contracts](SHARED_CONTRACTS.md) and
[account/deployment guide](docs/PRODUCTION_SETUP.md) describe the verified scope.
Historical milestones are in docs/history; retained v1 code/docs/tests preserve
the earlier deterministic/evidence work. Private v1 operations require an admin.

## Deployment

Follow [the deployment guide](docs/DEPLOYMENT.md) for verified local release checks,
Render/Windows instructions, private data transfer and recovery. The owner has
confirmed real admin access and SMTP authentication passes. No hosting was
provisioned. Current SQLite/worker/SMTP architecture cannot use Render Free or
Vercel Functions safely; the guide explains the additional migration for a free
hosted backend. The paid Render example is review-only, not an automatic deployment.
