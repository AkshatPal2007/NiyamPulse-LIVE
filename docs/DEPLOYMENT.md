# Deployment guide — stateful release candidate

Prepared 31 October 2026. Native Windows Python 3.12 is verified locally. Hosting
and the Linux branch of the runtime lock still require the actual platform/CI run.
No service, domain or paid resource has been provisioned.

## Choose a platform that preserves the application's state

This application stores accounts, immutable evidence and the spending ledger in
SQLite and runs bounded monitoring workers. Deploy the existing frontend and API
together at one HTTPS origin, with one process and durable storage.

| Option | Fit for the current implementation |
|---|---|
| Render paid web service + persistent disk | Supported deployment configuration; hosted execution still unverified |
| Windows host with durable disk + HTTPS reverse proxy | Supported native runtime; operator supplies TLS and process supervision |
| Render Free | Unsuitable for real accounts: local files are lost, idle workers sleep and SMTP ports are blocked |
| Vercel Functions | Unsuitable for this local SQLite/long-running-worker backend |
| Vercel static frontend alone | Does not provide the backend/database/monitoring service |

These constraints come from [Render Free](https://render.com/docs/free),
[Render persistent disks](https://render.com/docs/disks) and
[Vercel's SQLite guidance](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel).
Using only free services requires a further migration to durable external database/
evidence storage, HTTP email delivery and independently scheduled monitoring. That
migration is not implemented or claimed here. Do not accept real accounts on an
ephemeral preview or use artificial keep-alive traffic as a durability substitute.

## Verify and export the current Windows installation

Run from the repository root. The app can remain running during its online backup.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.build_release
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.operations smtp-check
.\.venv\Scripts\python.exe -m backend.operations preflight
.\.venv\Scripts\python.exe -m backend.operations backup
```

Preflight prints its mode: passing in `local` is not proof of a deployed production
service. The backup and its `.manifest.json` sidecar are private files under
`var/backups/`. They contain real account/evidence data and the complete financial
ledger. Keep both off Git and transfer them only through your authorized private
hosting channel. Copying only the live `.sqlite3` file can omit WAL transactions;
use this online backup command instead. Take a fresh export at cutover and stop
accepting local account/review changes until the hosted restore is complete.

## Render instructions for the current architecture

This path needs a paid compute plan and disk. Review the current charges yourself;
the agent has not purchased or configured hosting. The non-active example is
`deploy/render.persistent.example.yaml`.

1. Review and push the source changes to your GitHub repository. Exclude `.env`,
   `var`, backups and credentials. Let the Windows/Linux verification workflow run;
   resolve failures before release. Select Python **3.12**, Node **24** for builds.
   `.python-version` requests the current 3.12 patch from Render.
2. Create a Python web service from this existing repository, with repository root
   as its working directory. Choose a paid, always-running plan and attach a disk
   at `/var/data`. Use a single service instance. Set:

   - Build: `pip install -r requirements-production.lock.txt && python -m scripts.build_release`
   - Start: `python -m backend.serve`
   - Health path: `/api/v2/health/ready`

3. Enter the environment settings from `deploy/environment.production.example` in
   Render's private Environment screen. Copy the actual SMTP/Sarvam secrets there
   yourself. Initially omit `NIYAMPULSE_PUBLIC_URL` so the app uses Render's own
   HTTPS URL, or set it to your exact intended HTTPS domain. Never use localhost
   on the host. Keep `NIYAMPULSE_STORAGE_DURABLE=1` only with the disk attached.
4. The first boot can initialize an empty store with disabled source adapters and
   zero permitted AI spend. Before accepting users, privately transfer the backup
   and manifest to the host. In Render Shell, restore to a **new** directory:

   ```text
   python -m backend.operations restore --from-backup /var/data/import/your-backup.sqlite3 --target /var/data/restored/niyampulse.sqlite3
   ```

   Substitute the actual private filenames. The command refuses an existing target,
   verifies integrity and revokes sessions/action tokens. It preserves accounts,
   reviewed data, source configuration and the complete Sarvam ledger. Set
   `NIYAMPULSE_DATA_DIR=/var/data/restored` in Environment and redeploy. Do not
   overwrite an open database or run the old synthetic-data cutover command.
5. In Shell run `python -m backend.operations preflight` and
   `python -m backend.operations smtp-check`. Require READY in **production** mode.
   Health readiness must return 200 over HTTPS. Log in again; existing account
   passwords remain valid after restore. Privately verify email delivery from the
   hosted origin; a successful SMTP handshake alone is not an inbox check.
6. Verify the administrator dashboard, review queue and original evidence. Use an
   actual consenting learner to follow an exam, see an already-reviewed update
   and mark it read. A new notice remains held until human review. Confirm source
   heartbeat/check times continue while the browser is closed. Exercise an actual
   restart/redeploy and confirm accounts, notices and spending reservations survive.

Render's provider instructions: [FastAPI service](https://render.com/docs/deploy-fastapi),
[environment variables](https://render.com/docs/configure-environment-variables),
[Python version](https://render.com/docs/python-version),
[health checks](https://render.com/docs/health-checks),
[compute plans](https://render.com/docs/compute-plans).

The example uses `0.5c-512mb` and a 1 GB disk as a starting configuration, not a
load-tested capacity claim. Review actual disk/RAM use and expected traffic. The
one-process SQLite architecture is the release scope; horizontal scaling requires
database/worker changes. The launcher reads Render's PORT, disables access logs,
uses asyncio/h11 and bounds concurrent connections. Render supplies proxy forwarding
configuration; do not trust arbitrary forwarded headers on an exposed native port.

## Native Windows production host

Keep Python 3.12 and a patched Node LTS for building. Install the pinned runtime
dependencies, build the frontend, place the data directory on persistent storage,
and set the production environment to its actual HTTPS origin and absolute Windows
data path. Verify SMTP, preflight and a recovery drill. Run:

```powershell
.\.venv\Scripts\python.exe -m backend.serve
```

The default listener is `127.0.0.1:8000`; put your chosen TLS reverse proxy in
front, restrict backend access, and supervise the one process using your existing
Windows service tooling. No server software or machine security settings are
installed/changed by this repository. Run the API's integrated monitoring or the
standalone monitor, not both. The production runtime lock rejects duplicate workers.

## Ongoing operations and rollback

- Back up daily and before each migration/release. Keep encrypted off-host copies
  with access limited to operators; establish retention and account-erasure handling.
  Same-disk snapshots alone do not protect against losing that disk/account.
- To roll back code, use the preceding verified commit against a compatible schema.
  Schema changes need a tested recovery plan; do not restore old data silently.
- For recovery, stop accepting writes, restore a verified backup into a fresh data
  directory, switch the configured directory, restart, run preflight and check known
  evidence/accounts/financial totals. Restore invalidates all login/action tokens.
  Historical backups may predate deletions/password changes; apply the operator's
  erasure/recovery policy before reopening service.
- Retain the existing ₹50 cumulative reservation cap and the 500-credit floor.
  Current paid processing is paused. Do not initialize a second spending ledger,
  reset the cap, or infer the provider balance from the local ledger.
- Review delivery failures, request IDs, failed source checks, pending reviews,
  paused jobs and backup success. Health endpoints expose only booleans.
- Before public registration, finalize the operator's privacy/contact/retention
  information and adult/guardian policy. The checkbox is a self-declaration;
  direct child signup/verified parental consent and a legal/security audit are not
  implemented or claimed. Voice input/TTS are optional future features.

The repository is prepared for a **stateful deployment and operator acceptance**.
No public URL, hosted SMTP success, cloud restore/restart, load benchmark or security
certification has been fabricated. Linux CI and the chosen host must supply their
own verification results.

## Dependency audit boundary

The shipped frontend dependency audit is clean. Full npm audit reports three
moderate build-only findings from the [minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249)
through Redocly/openapi-typescript. Generator 7.13.0 stays pinned and consumes only
our trusted local Python-generated schema; none of it enters the shipped browser
code. Track an upstream compatible fix. Do not accept arbitrary remote schemas or
force major transitive replacements merely to suppress the report. This audit does
not certify the whole application's security.
