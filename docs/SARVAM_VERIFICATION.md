# Sarvam phase — observed verification, 31 October 2026 IST

## VERIFIED

The user supplied a key through ignored `.env` and authorized a total testing
budget of INR 50. Seven admitted paid operations are recorded locally: six
Sarvam-105B chat requests and one Document AI/Vision job. The budget reserves INR 5
per operation, currently INR 35/50. This is a conservative admission ledger, not
Sarvam's bill. Actual provider usage returned 11,605 prompt and 3,647 completion
tokens across the chat requests. Status/result GETs and cache reuse do not submit
new paid jobs. No additional provider or monthly subscription was configured.

Requests use fixed HTTPS Sarvam endpoints, bounded input/output, explicit timeouts,
no credential logging, strict candidate schema and persistent content/version cache.
The initial low output allowance was consumed by default model reasoning; explicit
`reasoning_effort: null` fixes that without claiming truncated output succeeded.

The captured UPSC Engineering Services (Preliminary) Examination, 2027 detail page
produced a candidate whose quotes resolve to the exact immutable extraction.
The model folded line breaks; a deterministic resolver accepts whitespace-only
changes only when there is a unique original span. It stores actual original
quotes and offsets. There is no fuzzy word/number/punctuation substitution.

The NTA PDF contains three pages. Its embedded PyMuPDF text is badly garbled,
including excessive whitespace. Its initial AI proposals failed literal checks.
A real Vision/Document AI job processed all 3/3 pages. The observed server uses
`type: digitise`, `page_num` and ordered blocks, which the installed SDK 0.1.41's
result union rejects. REST output is validated explicitly against page identity,
coverage, reading order, status and size. SDK submit/status calls remain in use.
The same completed job was resumed; client fixes did not resubmit the PDF.
HTML tables are converted to a new immutable text extraction, with earlier raw
PDF/extraction/OCR cache preserved. No bounding boxes are called verified.

NTA fact proposals STILL fail the exact evidence guard. They remain held and cannot
publish via UI or direct API. The outcome is recorded honestly as GUARD_REJECTED,
not as an end-to-end success. Human source review remains required even for UPSC.
No genuine source notice was approved or dispatched by the agent.

Controlled Hindi overviews use a closed dictionary of topics and exact source labels,
copying date/value strings verbatim and retaining original quotations. They do not
normalize ambiguous dates, decide eligibility or send uncontrolled prose to TTS.
English is extractive. Language preference selects reviewed, frozen summaries;
there are no per-subscriber model calls.

## Tests and UI verification

- **101 tests and 38 subtests passed** on native Windows Python 3.12 in 32.21s;
  TypeScript/Vite build, schema smoke, pip check and git diff check passed. Tests
  cover malformed output, incomplete reasoning
  responses, invented quotes/dates/cycles, role/stale writes, budget/quota errors,
  whitespace span resolution, tampered summaries, Hindi fan-out, OCR page coverage,
  source preservation, no-text retention and blocked publication after rejection.
- Regression cases were reproduced failing, then passed after fixes.
- Browser opened the production frontend from a temporary port 8001 server;
  actual UPSC source evidence, cache state, Hindi text and INR 35/50 reservations
  were visible. The NTA guard hold and OCR evidence were visible. A repeated NTA
  extraction used cache and left operations/reservations unchanged. No console
  errors were observed.
- Original user server on port 8000 was left untouched. Agent verification worker
  was disabled to avoid two source schedulers. Restart the user server to load new
  backend code and environment settings.

## ASSUMED / boundaries

The platform remains a localhost prototype with synthetic learner identities.
OCR output is untrusted machine text until an operator compares it with the PDF;
matching text to an immutable OCR record does not independently prove pixel-level
accuracy. Source host matching does not certify document authenticity.

## UNTESTED / deferred

Free-form Hindi translation and language evaluation, voice input/output, measured
accuracy, public authentication/child-consent, broad monitoring coverage and the v2
personalized-rule bridge remain unfinished. The preserved Python engine remains
sole authority for supported decisions. This phase creates no PASS/FAIL claims.

## Current human action

The synthetic Engineering learner is already subscribed to UPSC ESE 2027 with
Hindi preference, prepared through the actual UI. Inspect the real UPSC notice as operator. Open the official source and verify its exact
cycle and historical dates before approving with a review reason. Discovery does
not mean applications are currently open. Return to the subscribed learner inbox
to verify the actual alert. NTA stays held until its evidence issue is resolved.
