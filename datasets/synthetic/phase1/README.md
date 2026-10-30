# Phase 1 synthetic fixtures

These are invented notices and applicants for engine tests, not real scholarship
documents or measured production data. Six UTF-8 text files form three pairs:

| Case | Amendment | Expected overall changes |
|---|---|---|
| `marks_relaxed_en` | Marks 70% to 60%; four other rules preserved | FAIL to PASS; FAIL to UNKNOWN |
| `income_tightened_hi` | Maximum income INR 250000 to INR 200000 | PASS to FAIL |
| `documents_expanded_en` | Required ID to required ID and INCOME | PASS to FAIL; PASS to UNKNOWN |

JSON files contain curated rule IDs, target maps, effective dates, personas, and
independently authored gold outcomes. `backend.synthetic_demo` parses actual
clause values from text using a strict English/Hindi fixture grammar, constructs
Pydantic DTOs and measured SHA-256/character anchors, then runs the real planner
and evaluator. Gold labels are used by tests, never by the engine or preview.

**ASSUMED:** fixture mappings and source trust are curated test inputs. The demo
explicitly supplies content-bound verification hashes for these inputs only.
These hashes are assertions from a trusted caller, not signatures or authenticity
certificates. Calling the evaluator without them yields UNKNOWN.

**UNTESTED / future:** PDF extraction, OCR, provenance/source lineage, publication
chronology, human approval, atomic persistence and a production offline replay
flow. Text-file hashes must not be presented as PDF hashes, and fixture line
numbers are not PDF page positions. Each text source is one synthetic page;
bounding boxes are absent. No evaluation scorecard or baseline is produced.

From the project root in native Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.synthetic_demo
.\.venv\Scripts\python.exe -m backend.synthetic_demo --case marks_relaxed_en --json
```
