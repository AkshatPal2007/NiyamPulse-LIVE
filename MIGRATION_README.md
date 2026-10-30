# NiyamPulse v2 — migration kit for your existing Codex repository

## Purpose

This archive **reorients**, rather than replaces, your existing codebase. Previously the app was a PDF-first scholarship-amendment dashboard. Now it is a **multi-exam, source-monitored subscription and notification platform**. It must track school-student and engineering exams such as JEE Main, NEET UG, NDA, GATE, UPSC ESE and SSC JE, with extensible exam cycles and sources.

## What to hand Codex

1. Extract this ZIP **somewhere outside your active repository**, e.g. `C:\Projects\niyampulse-migration-kit`.
2. Give Codex the whole directory or copy files in a new branch. **Do not overwrite your existing AGENTS.md or schemas.py blindly.**
3. Paste `CODEX_MIGRATION_PROMPT.md` into Codex. It directs Codex to inspect and migrate the existing repository conservatively.
4. Keep the old code in source control; `backend/legacy_schemas_v1.py` is an additional compatibility copy, not a replacement for Git history.

## Native Windows PowerShell smoke test (kit alone)

```powershell
cd C:\Projects\niyampulse-migration-kit
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-contracts.txt
.\.venv\Scripts\python.exe -m backend.schemas
.\.venv\Scripts\python.exe -m pytest -q
```

This package contains **data models and contract tests**, not an operational crawler, HTTP server, real users or notifications. The generated `exam_catalog.json` lists suggested exams; `source_registry.json` leaves all web adapters disabled.

## Key decisions

- `/api/v2` introduces subscriptions/notices/notifications; old `/api/v1` endpoints should keep working until intentionally retired.
- `backend/legacy_schemas_v1.py` preserves prior five-rule union and evidence semantics; new `backend/schemas.py` composes with it.
- All web-source listing URLs were found on official sites as of 2026-10-30, but scraping compatibility, API access and recurring monitoring are **not tested**.
- Distinguish ordinary notice updates from eligibility impact. Most JEE/NEET/GATE announcements need a reliable subscription notification, **not a fabricated PASS/FAIL decision**.
- The label "official" means published on a source that matches configured evidence, never a guarantee of authenticity.
