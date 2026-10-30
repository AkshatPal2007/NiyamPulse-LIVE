# NiyamPulse LIVE

One scholarship notice changes; deterministic Python shows exactly which synthetic
applicant decisions changed, with literal source evidence. Decision support only;
not official approval.

**Implemented:** Phase 1 engine and Phase 2 local backend. **Next:** Phase 3 frontend.
No frontend, Sarvam/OCR, Hindi speech or measured evaluation scorecard exists yet.
Read `AGENTS.md`, `SHARED_CONTRACTS.md`, and `PROGRESS.md` before changing code.

## Native Windows setup and start

From this project directory in PowerShell, with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m backend.demo_setup
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

If your environment already exists, skip its creation. Activation is optional.
Open [interactive API documentation](http://127.0.0.1:8000/docs). The API base is
`http://127.0.0.1:8000/api/v1`. This phase is a local operator service; account
authentication and production deployment are not implemented.

Setup creates the declared synthetic workspace `scholarship-demo-2026`, five
synthetic profiles, three PDFs in `output/pdf/`, and the watched amendment folder
`var/intake/`. **It never imports, reviews or applies any notice.** Repeating setup
preserves state; it does not reset an already reviewed demo. For a fresh isolated
run, set `$env:NIYAMPULSE_DATA_DIR = 'var/demo-2'` before setup and server startup.
Use a different data folder rather than deleting an existing database.

## Manual Phase 2 walkthrough

Use **Try it out** in the API documentation, replacing the path parameters:

1. `GET /api/v1/workspaces/{workspace_id}` with workspace ID
   `scholarship-demo-2026`. Revision starts at 0, with UNKNOWN decisions.
2. `POST .../documents`: select `output/pdf/synthetic_original.pdf`, set `kind`
   to `ORIGINAL`, and leave `source_url` absent. HTTP 202 means queued, not verified.
   Copy the returned `document.document_id`.
3. Poll the workspace. Inspect the original's `source_gate.checks`, the stored PDF
   at `.../documents/{document_id}/pdf#page=1`, and its `/extraction` endpoint.
   Page numbers are 1-based; literal offsets refer to immutable page text.
4. Explicitly review the original using `POST .../documents/{document_id}/review`:

   ```json
   {
     "expected_workspace_revision": 0,
     "reviewed_by": "your_operator_name",
     "confirm_source_review": true
   }
   ```

   This bootstraps the verified baseline at revision 1. The name is a local
   operator assertion, not an authenticated identity.
5. Copy `output/pdf/synthetic_corrigendum.pdf` into `var/intake/`. The running
   watcher will detect the new bytes, record SHA-256 and acquisition metadata,
   extract them and prepare an amendment. It **never applies automatically**.
   Alternatively, upload it through `/documents` with `kind=CORRIGENDUM`.
6. Read the workspace's `amendment_id`, then call
   `GET .../amendments/{amendment_id}/preview`. Inspect source checks, targets and
   actual before/after decisions. Expect 5 evaluated, 2 changed: 1 improved and
   1 review-required; 3 unchanged. These are synthetic fixture outcomes.
7. After reviewing the source, explicitly call `POST .../amendments/{amendment_id}/apply`
   with revision **1**, your name and `confirm_source_review: true`. The transaction
   returns revision **2** and one persisted APPLIED event.
8. Read `/events`, then use its opaque `next_cursor` to poll without replaying old
   events. Try `/timeline?as_of_date=2026-10-14` and `2026-10-15` to inspect the
   effective-date boundary. An optional aware `known_at` selects committed knowledge.
9. Upload `output/pdf/synthetic_mismatch.pdf` as a corrigendum. Its authority check
   fails, so it is quarantined and cannot change rules, decisions or events.

The watcher folder accepts **corrigenda only**. Originals use the explicit upload
and original-review flow. Only locally configured acquisition channels or configured
file hashes can pass the origin check. A user-supplied URL never establishes trust.
Configured-source matching is not proof of cryptographic authenticity.

## Supported parsing and truthful degraded behavior

Phase 2 supports a strict `NIYAMPULSE [SYNTHETIC] NOTICE v1` PDF text format. See
`backend/demo_fixtures.py` for literal headers and closed rule syntax. RULE belongs
to originals; ADD, REPLACE with a target/new ID, and REVOKE belong to corrigenda.
English and Hindi clause grammars are shared with Phase 1; actual Phase 2 PDF
integration tests currently cover English only. Arbitrary administrative prose,
unsupported conditions, scans needing OCR and malformed dates are held for review
or fail visibly. No rule subset from a failed document can be activated.

PDFs are limited to 10 MiB / 20 pages. Source bytes, extraction snapshots,
acquisition records, committed snapshots and events have append-only SQLite guards.
Extraction caches use PDF hash and extractor version, not filenames. Cached work is
labeled `CACHED_EXTRACTION`; new local work is `LOCAL_PDF`. No live Sarvam call is
claimed. PDF boxes are deliberately empty; the API supplies page + exact quote
without asserting verified coordinate highlighting.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m backend.synthetic_demo
```

Tests use isolated databases and synthetic inputs. They cover engine boundaries,
real PDF extraction, source/value checks, unreviewed/invalid inputs, rollback,
concurrent apply, history, cached extraction, restart recovery and the actual
Windows watcher. See `PROGRESS.md` for observed versions, counts and limitations.
`/evaluations/latest` returns a typed 404 until a genuine evaluation run exists.

`MODEL_HANDOFF.md` contains a copyable prompt for another model.
