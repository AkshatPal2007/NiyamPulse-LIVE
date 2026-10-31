# NiyamPulse judging guide — 31 October 2026

## What the product does

Students/adult account holders follow exam cycles. NiyamPulse watches configured official sources, retains source evidence, extracts information using Sarvam, routes reviewed notices to matching subscribers, and shows original-source dates. A late follower can inspect existing reviewed updates immediately. It is decision support, not official eligibility/application confirmation.

## Feature inventory

| Feature | Current scope and evidence |
|---|---|
| Real identity | Verified email, password login/recovery, revocable sessions, owner-only account data and administrator role; no demo personas/default passwords |
| Exam discovery | Searchable multi-exam catalog with separate years/sessions and honest catalog-only coverage |
| Following | Multiple cycles, topic preferences, pause/resume, unsubscribe and self-reported application status |
| Exam brief | Existing reviewed source notices/quoted dates visible after following; older dates may be past/superseded |
| Personal inbox | Cycle/topic matching, persistent delivery/read state and deduplication |
| Official monitoring | NTA JEE, NTA NEET and UPSC exercised; allowlisted fetches, source hashes, snapshots, dedup, hourly cadence and worker health |
| Operator workflow | Source health, intake/review queue, extraction/OCR controls, human publication review, recipient/delivery counts |
| Sarvam 105B | Structured classification/extraction and guarded Hindi explanations; invalid outputs stay blocked |
| Sarvam Vision | Cached OCR recovery for scanned PDFs; no invented highlights/coordinates |
| Voice | Saaras is the default microphone-query path; Hindi/Hinglish filters exam/year/session/topic. Optional browser recognition is separately labeled and opt-in. Typed queries share the deterministic notice-search endpoint |
| Narration | Bulbul v4 Flash on reviewed summaries with source/date guards, exact text and cache labels; actual JEE administrator-preview audio prepared |
| Source viewer | Authenticated captured PDF/page preview, hash checks, literal native-text highlights; OCR-only sources show no invented coordinates |
| Deterministic impact | Five closed rule types, opt-in adult-own fields, four decision states and recorded before/after checks. General news is not PASS |
| Evaluation | Persisted declared-synthetic 3-case/13-profile transition/count/replay agreement; not real-world/OCR/classification accuracy |
| Privacy/operations | Optional personalization, erasure/deletion, public contact, backup/restore, startup preflight, health and worker locking |

## Genuine data prepared

- 13 captured official notices; 2 approved updates (JEE registration and UPSC ESE schedule).
- 2 real accounts (one administrator and one learner), 8 subscriptions, 2 persisted notifications at the verification snapshot. Counts can change through real use; do not hardcode them.
- JEE Main 2027 Session 1: owner compared the source PDF and explicitly approved publication. Application window quoted as 24 October–22 November 2026 up to 11:50 P.M.; examination dates 20,21,22,23,24,28 January 2027. Link and dates are in the source-backed app update.
- Existing UPSC ESE 2027 update remains published. Its application deadline is historical; do not present it as still open.
- Successful source polls: NTA JEE 08:32:03 UTC, NTA NEET 08:32:06 UTC, UPSC 08:32:13 UTC on 31 October (14:02 IST). No new notices; UPSC check returned duplicates/unmapped older cycles, no errors. Unmapped cycles remain unclaimed.
- Other NEET notices include scanned, guard-rejected, rule-review or historical material. They were not mass-approved. Machine-readable per-notice review packet: var/qa/judging-review-packet.json (local, ignored).
- Backup taken before JEE publication under var/backups; preserve the manifests and entire financial ledger.

## Before the judges arrive

1. Keep the laptop powered, awake and connected. Use localhost/127.0.0.1 or HTTPS; plain HTTP on a LAN IP will not support microphone access. Check the correct microphone and browser/Windows permissions.
2. Backend is already restarted on port 8000. Refresh the frontend after the final build. If starting afresh, use `.\.venv\Scripts\python.exe -m backend.serve` from the repo root. Do not run a second source worker.
3. Open the real administrator and real learner accounts in separate browser profiles/private windows. Never reveal passwords, .env or API keys on screen. Do not invent extra attendees/users to inflate metrics.
4. In the learner account confirm JEE Main 2027 Session 1, its exam brief and inbox alert. Owner already confirmed these and the captured PDF preview after restart. Already-read alerts remain read; do not reset state to simulate delivery.
5. Check voice on the actual device. Ask “JEE Main session 1 ki registration last date kab hai?”; stop recording to send to Saaras and search. Leave optional browser speech unchecked when demonstrating Sarvam. Confirm the transcript/search results. Typed search is the fallback.
6. Play a short narration excerpt and compare spoken dates with the exact written text. Administrator JEE narration is cached; learner/language-specific requests may need a separate live call. Do not claim pronunciation is independently certified.
7. For live paid features refresh Billing first and record a genuine current balance through the operator UI. The last provided 595 balance expires 15 minutes after recording. Preserve 500 credits; no stale snapshot refresh or budget bypass.
8. Keep the source brief and PDF loaded in advance. Existing reviewed data and cached pages work without a fresh remote poll; live microphone transcription/new synthesis do require connectivity/provider access.

## 90-second sequence

- **0–10 s:** Explain the missed-deadline problem and show the exam directory with real source coverage labels.
- **10–30 s:** Show JEE 2027 Session 1 followed by the learner; open its existing date brief. Explain that late subscribers still see published registration information.
- **30–45 s:** Show the JEE inbox update, quoted dates and captured PDF. Open the original source if network permits. Mention review before publication.
- **45–60 s:** Ask the Hinglish deadline question using Saaras, or transparently use the identical typed search if device/network access fails. Show matching official notice, not a generated eligibility answer.
- **60–70 s:** Play a few seconds of source-backed Bulbul narration; show the exact text/cache label.
- **70–85 s:** Switch to operator: real source health, 13 discoveries, 2 approved updates and genuine delivery/read counts. Show one blocked notice as abstention/evidence protection; do not approve it to manufacture a live event.
- **85–90 s:** Explain that Python determines relevance/closed-rule impacts; AI extracts/explains. Show the declared synthetic evaluation scope if time allows.

There is no guaranteed new official announcement during a judging slot. Describe the real already-completed discovery/review/publication and current persisted state honestly. Do not stage a fake network success, notification or recipient count.

## Verified checks and limits

- Native Python suite: 219 passed + 38 subtests, 51.24 seconds; one existing TestClient deprecation warning.
- Final TypeScript/Vite build, schema generation, seven immutable source capture hashes and pip check pass. Local preflight READY, including DB integrity, administrator, no synthetic runtime records, SMTP configuration and financial ledger.
- Owner confirmed learner follow/brief/inbox/read and actual captured PDF preview. Owner subsequently confirmed voice search and narration work on the real device.
- Screenshot 404 was an old backend process: after owner restart protected routes returned 401 for anonymous requests, as expected. Missing-route UI now gives restart guidance; source cooldown/concurrent-worker CLI checks return DEFERRED without traceback.
- No software can be certified error-free by these checks. No public deployment, complete source coverage, full security/legal certification or real-world eligibility accuracy is claimed. Three previously tracked moderate build-only dependency advisories remain; production audit was zero at the previous check.
