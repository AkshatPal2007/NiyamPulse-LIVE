# Existing repository audit — 30 October 2026

## Observed baseline

Git was clean at `70ada56`. The repository contained a native Windows FastAPI /
Pydantic 2 / SQLite backend, 61 passing tests, three synthetic PDFs and text
fixtures. There was **no frontend**. No Sarvam integration or web crawler existed.
The baseline suite passed again before migration on Python 3.12.10.

| Existing work | Migration decision |
|---|---|
| Five-rule evaluator, amendment planner, impact classification | Preserve code and behavior; reuse only for actual validated rule amendments |
| PyMuPDF extraction, literal anchors and content fingerprints | Preserve; reuse extraction and evidence validation for v2 notices |
| Revision checks, transactional SQLite and immutable records | Preserve v1; extend the same database with separately named v2 tables |
| `/api/v1` and synthetic original/corrigendum demo | Keep functional as legacy/operator tooling; remove from the main subscriber journey |
| Current `backend/schemas.py` v1.1.0 | Preserve byte-for-byte as `backend/legacy_schemas_v1.py`; v1 services import it explicitly |
| Migration kit's older legacy schema | Do not overwrite our newer tested v1.1.0 with it |
| React/UI | Missing; add a new frontend for the new product, without replacing backend work |
| Web monitoring, account ownership, subscriptions, inbox | Missing; implement as v2 services and routes |

V1 documentation is preserved under `docs/legacy-v1/`; the kit's original status
ledger is retained as `docs/MIGRATION_KIT_PROGRESS.md`. Root instructions/contracts
now describe the authorized v2 direction. V1 API version remains 1.1.0; v2 uses 2.0.0.

## First slice

Local synthetic persona session → public exam catalog → owned multi-cycle/topic
subscription → actual or clearly labeled recorded notice discovery → operator
review with optimistic revision → deterministic cycle/topic fan-out → persisted
in-app alert → mark read → database-derived admin counts.

Informational updates have GENERAL_UPDATE relevance and no invented decision pair.
V2 personalized rule-change publication is held until its full validation bridge
exists. The earlier authoritative engine and all its tests remain in place.

## Verification after contract merge

- `python -m unittest discover -s backend/tests -q`: **61 passed**.
- `python -m pytest tests/test_schema_contracts.py -q`: **8 passed** on Windows.
- `python -m backend.schemas`: v2 imports/JSON Schema generation passed.
- Direct HTTP GET observed NTA listing **200** and UPSC listing **200**. These
  probes are not yet evidence that a recurring source adapter is implemented.
- NTA robots allows the public listing; UPSC robots redirects to the homepage,
  which requires explicit recording as a nonstandard robots response.

No files or database rows from the v1 implementation were deleted. No remote
repository push or hosted deployment is part of this local migration slice.
