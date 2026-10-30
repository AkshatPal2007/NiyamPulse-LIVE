# Current model handoff — NiyamPulse v2

Work in the existing native Windows Python 3.12 repository. Read `AGENTS.md`,
`SHARED_CONTRACTS.md`, `PROGRESS.md`, `README.md` and `docs/MIGRATION_AUDIT.md` first.
The product direction has changed: it is now a multi-exam subscription and
source-monitored in-app notification platform. Do not return to upload-first
scholarship development as the main experience.

The earlier backend is preserved, including the five-rule deterministic evaluator,
PDF extraction/evidence handling and 61 tests. The original schema 1.1.0 is in
`backend/legacy_schemas_v1.py`; v1 services import it explicitly. V2 schemas compose
with it and preserve `/api/v1`. V2 tables are additive; `backend/storage.py` remains
an existing module, not a directory to overwrite. V1 docs are archived.

The first v2 informational slice is implemented: public multi-exam catalog; opaque
local demo sessions; user-owned cycle/topic subscriptions; optional opt-in profile
and erasure; private paginated inbox/read state; operator-only evidence review;
revision/idempotency checks; deterministic matching; atomic in-app notification
fan-out; database-derived admin totals/charts. V2 DTO/API version is 2.0.0. Update
schemas and SHARED_CONTRACTS together for public changes.

Actual NTA JEE Main and UPSC adapters were fetched and exercised on native Windows.
Each discovered/extracted one mapped 2027 notice; older UPSC items stayed unmapped.
They are enabled locally on hourly polling; config defaults remain disabled for a
fresh setup. The worker is independent of the browser and can run as a standalone
process. See `docs/SOURCE_VERIFICATION.md` for exact hashes, timestamps and robots/
site-policy observations. Do not claim cryptographic authenticity or all-exam
coverage. No protection bypass, application automation or paid service was used.

Frontend is React/TypeScript/Vite/Tailwind with types generated from actual OpenAPI.
It has separate responsive student and operator views. A real browser walkthrough
verified JEE/GATE subscriptions, synthetic JEE review, correct exclusion of the
GATE-only learner, delivery, evidence and READ. Original live notices stayed pending.

All demo identities are synthetic and prominently labeled. Local demo role
selection is not production authentication. No DOB/marks/income is required to
subscribe. The disclaimer is: Decision support only; not official eligibility or
application confirmation. GENERAL_UPDATE never contains invented eligibility
before/after states. The existing Python engine is still authoritative.

DONE IN SARVAM PHASE: live authenticated 105B requests, Vision OCR on all three
NTA PDF pages, bounded cached candidates, exact-quote guards, deterministic Hindi
labels/value copies and reviewed language fan-out. The actual UPSC candidate
validated; NTA candidate proposals remain rejected/held. No genuine source notice
was approved or dispatched. ₹50 cap authorized; ₹35 reserved across 7 admitted
operations (not actual billing). See docs/SARVAM_VERIFICATION.md.

NOT DONE: free-form Hindi/audio evaluation, production
login/consent, v2 validated personal-rule publication, deep attachment crawling,
more adapters, broad archive coverage and measured evaluation. Current notice
summaries are source excerpts. Rule-like notices requiring the v2 bridge are held,
not published through an informational workaround. No per-subscriber LLM calls.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.export_openapi
npm --prefix frontend run types
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --env-file .env --host 127.0.0.1 --port 8000
```

The backend serves the built frontend at `/`. Development UI: `npm --prefix frontend
run dev`, port 5173, with an API proxy. Standalone source worker: `python -m backend.monitor`.
Do not run two worker modes together. Credentials stay in local environment variables;
never put them in chat, source files or frontend bundles.

Check current Git status and progress for exact latest test totals. Preserve working
code and user changes. Do not push, deploy publicly or use paid credentials without
authorization. Continue the next smallest authorized increment, not a restart.


Current manual gate: user must inspect and approve/reject the real UPSC notice as
required by AGENTS invariant 3. Keep the NTA guard hold. User's pre-existing port
8000 server was not stopped; it must be restarted to load new backend code. Only
stop agent-owned port 8001 verification server. Do not reset the user's additional
synthetic reviews/subscriptions. Continue remaining phases after human review;
do not imply the entire project or the v2 rule bridge is complete.

Latest native result: 101 tests + 38 subtests passed; production UI build, schema
smoke, pip check passed. Engineering learner is prepared with an actual ESE 2027
subscription and Hindi preference; user only needs real source review/approval
before opening that learner inbox. This setup added no personal applicant data.
