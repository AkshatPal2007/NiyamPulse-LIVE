# NiyamPulse v2

**Your exams. Your updates. One clear view.**

A local, source-linked exam-notification platform for school students and
engineering aspirants. The first working flow is:

**Choose exam cycles → subscribe → discover a notice → operator review → matching
learner inbox → read status and actual admin counts.**

The earlier scholarship engine/backend is preserved. `/api/v1` stays operational;
its documentation is in `docs/legacy-v1/`. The new experience uses `/api/v2`.
Read `AGENTS.md`, `SHARED_CONTRACTS.md` and `PROGRESS.md` before changing code.

## Start on native Windows

From the project root in PowerShell, using the existing Python 3.12 environment.
Create `.env` from `.env.example` and enter your Sarvam key locally:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm --prefix frontend ci
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --env-file .env --host 127.0.0.1 --port 8000
```

Open [NiyamPulse](http://127.0.0.1:8000/) or
[API documentation](http://127.0.0.1:8000/docs). The backend serves the built UI
and runs the source worker independently of the browser. No Docker/WSL is needed.
On this machine dependencies and the UI build have already been prepared.

For frontend development, keep the API running and use a second PowerShell:

```powershell
npm --prefix frontend run dev
```

Open [Vite development UI](http://127.0.0.1:5173/). It proxies `/api` to port 8000.

## Local demo identity and privacy

The top-right persona picker switches among **synthetic** school learner,
engineering learner and platform operator accounts. These are real local database
records with expiring opaque sessions and role/ownership checks. They are not a
production login system. Keep this prototype bound to loopback.

Subscriptions require no DOB, marks or income. Optional profile data needs explicit
opt-in. Personalization removal and account deletion are implemented. Removing a
learner revokes their sessions and deletes their subscriptions/inbox; restarting
will not silently recreate that deleted account.

`APPLIED_SELF_REPORTED` is a learner assertion, never official application status.
Every result view includes: **Decision support only; not official eligibility or
application confirmation.**

## A short end-to-end walkthrough

1. Select **School learner**, open **Explore exams**, follow JEE Main 2027
   Session 1. Choose topics if needed. More than one exam/cycle may be followed.
2. Select **Engineering learner**, follow GATE 2027. GATE is catalog-only until
   its own adapter is independently verified; this does not imply live coverage.
3. Select **Platform operator** and click **Replay synthetic notices**. This
   creates two explicitly labeled test notices, not a fake official fetch.
4. Inspect the synthetic JEE notice. Read its evidence, enter a review reason,
   confirm the exact cycle, then **Approve & notify matching subscribers**.
5. Switch to the school learner: the JEE alert appears. Open it to persist READ.
   The GATE-only engineering learner receives no JEE alert.
6. Return to the operator dashboard. Delivery/read/chart values come from actual
   database records. The source queue also contains genuine notices if monitored.

The automated browser QA already exercised this path in the local database: two
subscriptions, one synthetic JEE publication, one delivered/read alert. Genuine
NTA/UPSC notices remain pending human review. Replaying is idempotent and does not
reset or manufacture fresh notices on each click.

## Real official-source monitoring

NTA JEE Main and UPSC active examinations have each completed a real native fetch,
parse and extraction run. See `docs/SOURCE_VERIFICATION.md` for URLs, timestamps,
raw hashes, robots behavior and coverage boundaries. These two sources are enabled
in this machine's local runtime database; new checkouts start with all disabled.

To verify and enable those adapters on a fresh local data directory:

```powershell
.\.venv\Scripts\python.exe -m backend.monitor --check nta-jee-main --discover --enable
.\.venv\Scripts\python.exe -m backend.monitor --check upsc-active --discover --enable
```

Enablement requires an actual mapped discovery with no processing errors. An
already enabled source that is not due returns a cooldown rather than polling
again immediately. Default interval is 60 minutes. Captured older/ambiguous exam
cycles are not routed to current subscribers. Only reviewed notices publish.

The API normally runs the worker. To run it separately while the API is closed:

```powershell
.\.venv\Scripts\python.exe -m backend.monitor
```

Run one worker mode at a time. If using the standalone process alongside the API,
set `$env:NIYAMPULSE_WEB_MONITOR = '0'` before launching the API. Set
`NIYAMPULSE_DATA_DIR` consistently for both processes to select another local
SQLite directory. Closing the frontend does not stop the worker.

The source registry is an initial catalog, not a coverage guarantee. NTA covers
its configured listing and linked PDFs; UPSC covers active-exam detail pages.
Deep attachment changes, archive pagination and additional publishers are future
work. Downloads are bounded, exact-host allowlisted and redirect/DNS checked.
Source matching is not cryptographic authenticity or publisher endorsement.

## What is and is not implemented

- **Implemented:** preserved five-rule evaluator; v2 catalog, owned subscriptions,
  optional profile/erasure, private inbox/read state, operator review, deterministic
  cycle/topic fan-out, transactional in-app delivery, immutable evidence, two live
  source adapters, independent scheduling and responsive learner/operator UI.
- **Held:** v2 personalized rule-amendment publication. Until the reviewed evidence
  bridge exists, rule-like notices requiring it cannot be approved as a shortcut.
- **Implemented Sarvam phase:** bounded cached 105B extraction and Vision OCR,
  exact source guards, controlled Hindi overviews and reviewed language fan-out.
  Genuine UPSC analysis validated; genuine NTA OCR completed but its fact
  proposals remain held by evidence guards.
- **Not implemented:** free-form Hindi/audio evaluation, public authentication,
  all-exam monitoring, personalized v2 rule publication and measured evaluation.
  No LLM decisions or per-subscriber LLM calls are made.

## Tests and generated frontend types

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
npm --prefix frontend run build
```

Tests include the 61 preserved v1 cases, the supplied contract tests, captured
source fixtures, HTTP failures/SSRF/redirects, dedup, topic/ownership gates,
privacy deletion, rollback, idempotency and signed inbox pagination. No test calls
Sarvam or performs real official application actions. Genuine network verification
is recorded separately from mocked/captured adapter tests.

See `PROGRESS.md`, `docs/MIGRATION_AUDIT.md` and `MODEL_HANDOFF.md` for current state.


## Sarvam configuration and the real-notice review gate

The local key is in ignored `.env`; never paste it into chat or frontend settings.
The user authorized a ₹50 testing cap. This cap persists in SQLite and is not reset
by a restart. `python -m backend.analyze` reports genuine request/token records and
local reservations; these are not a provider bill. Current reservation is ₹35.

Explicit local operator commands (not an automatic publication loop):

```powershell
.\.venv\Scripts\python.exe -m backend.analyze
.\.venv\Scripts\python.exe -m backend.analyze --notice STORED_NOTICE_ID
.\.venv\Scripts\python.exe -m backend.analyze --notice STORED_NOTICE_ID --ocr
```

The admin review modal also offers these actions. Repeated unchanged extraction
uses the immutable cache; OCR resumes/reuses a stored job. Every paid admission
reserves ₹5 and is blocked if it would exceed the configured cap. OCR is limited to
five stored PDF pages in this slice. A rejected candidate cannot publish.

The synthetic **Engineering learner** is already following **UPSC ESE 2027** with
Hindi preference for this walkthrough. As operator, open the real UPSC
notice and original source, compare the source/cycle/evidence, enter your own
review reason and approve only after checking it. Switch back to the subscriber
and inspect the actual inbox alert. This notice contains historical source dates;
its discovery does not mean applications are currently open. NTA remains held.

See `docs/SARVAM_VERIFICATION.md` for verified outcomes and limitations.
