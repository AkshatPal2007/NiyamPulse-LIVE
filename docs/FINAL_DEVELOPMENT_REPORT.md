# Final development increment — 31 October 2026

This increment completes the bounded core feature work and UI refinement. It does not claim every research/coverage item in the future plan is complete. The pre-validation implementation summary was delivered before the final checks.

## DONE — implemented

- Editorial frontend: paper/ink/cobalt palette, serif display type, numbered exam directory, genuine reviewed bulletin, compact workspace tables, responsive account/settings/evidence views, restrained actual-transition motion and reduced-motion support. Existing source and account components were reused.
- Optional personalization UI: explicit opt-in, adult account holder DOB, marks, integer INR income, document codes and known-complete inventory. Opt-out/erasure clear fields. Real-runtime personal DOB under 18 is rejected; guardians follow exams without supplying a child's data.
- Account menu now fetches the current profile before opening settings. Existing subscriptions can edit topics, including supported eligibility-change updates, and use UNKNOWN self-reported application status.
- Actual bridge before/after RuleCheck arrays survive fan-out and JSON storage. Four states and unchanged historical evaluations are displayed accurately; general news remains GENERAL_UPDATE. Older alerts without recorded checks say so.
- Authenticated original PDF/page preview. Source SHA-256 is checked; only exact native-text quote matches receive highlight coordinates. HTML/unsupported/OCR-only inputs retain links/excerpts without invented highlights or executable HTML previews.
- Saaras v4 voice search: explicit browser recording/transcription consent, bounded PCM WAV, visible transcript, confirmed catalog search. It cannot subscribe, approve or modify an account.
- Bulbul v4 Flash: owned-alert narration and administrator preview of approved updates. Exact reviewed summary, literal numeric/date and informational-assertion guards run before synthesis; text fallback and exact text sent remain visible. Codec validation is not proof of pronunciation fidelity.
- Voice uses the existing shared ledger, timeouts, rate limits, 500-credit floor and cache. Recordings/transcripts are not persisted by the app; source-only generated audio is cached. No key reaches the browser.
- Real persisted synthetic evaluation route/panel: the existing parser, amendment planner and deterministic evaluator run twice against three declared text pairs/13 supplied profile labels. No production users or notices are created.
- Owner-approved public support email configured privately through PUBLIC_SUPPORT_EMAIL; example documents the optional field.

## VERIFIED — observed evidence

- Native Windows Python 3.12.10: `python -m pytest -q`: **209 passed, 38 subtests passed**, 78.97 s. One existing Starlette/httpx TestClient deprecation warning.
- After cache/dataset-boundary cleanup and strengthening fan-out persistence coverage: `python -m pytest -q tests/test_v2_rule_bridge.py tests/test_finish_features.py`: **37 passed**, 6.89 s.
- `python -m backend.schemas`, `python -m scripts.export_openapi`, `npm --prefix frontend run types`, final TypeScript/Vite build and `python -m pip check` pass.
- `python -m scripts.verify_captures`: **7 immutable source hashes verified**. `git diff --check` passes.
- `npm --prefix frontend audit --omit=dev --audit-level=moderate`: **0 vulnerabilities**. Previously tracked three moderate build-only transitive advisories remain; no force override/downgrade was applied.
- `python -m backend.evaluate` persisted run eval-72b46b132e004a91bd0181a8f9598676: **13/13** supplied transitions, counts agree, repeated replay agrees. Dataset SHA-256: ca6060dceb8929448006482183c52d19f48ce43d6bbf9be18f677d78a72d624f.
- This metric covers supplied synthetic text labels only. It is not OCR/classification/source-authenticity/matching accuracy, a comparative baseline, or real-world eligibility accuracy. Gold labels still require independent maintainer review.
- Real paid Bulbul call on the existing approved UPSC update returned a **2,886,830-byte valid WAV**; real Saaras call on a resampled 20-second clip returned **179 transcript characters**, language hi-IN, action_taken=false. No user microphone recording was needed. Audio pronunciation was not human-certified.
- User supplied a refreshed **596.96-credit** snapshot before speech checks. Observed ledger afterward: **14 admitted operations / 7000 paise conservative total reservations**; floor remains 500. Estimated remaining after the two holds: 586.96, not a provider-billed wallet reading. Snapshot expires after 15 minutes.
- Browser checks: desktop two-column hero, 390px phone layout, mobile menu, NEET search, sign-in layout, public contact/privacy. No horizontal document overflow. Proof: ../output/screenshots/final-premium-home.png and final-premium-mobile.png.
- Owner manually confirmed the real account menu opens Settings, optional profile section appears, and administrator overview shows the persisted evaluation report.
- QA used owned loopback port 8001 with monitoring disabled. The owned QA process/tab were stopped/closed after checks; temporary viewport override reset. The user's normal backend and data were preserved. No new notice approval/publication or fabricated account/notification occurred.

## PARTIAL — release acceptance and wider scope

- Restart the normal backend after this update; the new routes are Python code, so replacing frontend assets alone is insufficient. Use the existing `.venv` and `python -m backend.serve`.
- Test a real learner's new subscription/topic change/inbox/read flow and microphone permission on the intended browser/device. Compare generated narration against the exact written source before relying on pronunciation.
- Human source review remains required for newly discovered notices and evaluable rule changes. More catalog exams need individually verified, cycle-specific adapters; currently exercised publishers remain NTA and UPSC.
- Broader independent gold corpus, OCR/classification/matching measurements, comparative baseline, capacity/operational/security review and consent-reviewed direct child accounts remain future work.
- Owner chooses deployment. Verify the actual HTTPS origin/proxy, private secrets, durable local data/backups, SMTP links, laptop/tunnel availability, background monitoring with browser closed and restart recovery. No public deployment was made.
- Public contact is configured. The operator must finalize the actual backup retention and adult/guardian privacy policy before public release; do not invent a retention promise or legal certification.
- Owner reported baseline GitHub CI green; this new increment still needs the owner's commit/push and fresh CI run. No Git push was performed.
