# NiyamPulse v2 demo video runbook

Prepared 31 October 2026 for a local, real-account product demo.

## Recording destination

Save the final recording as:

```text
output/demo-video/NiyamPulse-v2-demo.mp4
```

Create `output/demo-video` before recording. Keep the unedited capture separately as
`output/demo-video/NiyamPulse-v2-demo-raw.mp4`. These are local recording paths;
upload the final MP4 to the judging/submission platform yourself.

## Before recording

1. Start the project from the repository root in PowerShell:

   ```powershell
   .\.venv\Scripts\python.exe -m backend.serve
   ```

   Use one running stack. Do not start a second monitor process alongside it.
2. Open `http://127.0.0.1:8000/`. Sign into the real learner account in one browser
   profile and the real administrator account in a separate profile. Never show
   passwords, inbox contents, personal account details, `.env`, API keys, or browser
   password managers in the recording.
3. Refresh each workspace. Verify that the JEE Main 2027 Session 1 brief, its
   reviewed source-backed update, the captured PDF preview, and the learner inbox
   alert are available. Use current counts shown by the app; do not quote counts from
   an older screenshot or script.
4. Check the exact dates on-screen before recording. The previously owner-reviewed
   JEE source states the application period as 24 October–22 November 2026 up to
   11:50 P.M., and exam dates 20, 21, 22, 23, 24 and 28 January 2027. These dates
   may be historical or superseded by the time you record. If so, explain that the
   app preserves source context and direct viewers to the linked official notice;
   do not describe an expired deadline as upcoming.
5. Set browser zoom around 90–100%, close unrelated tabs, hide bookmarks and clear
   desktop notifications. Use a clean browser profile with no saved credentials
   visible. On-screen personal account identifiers should be hidden or cropped.
6. For voice, test microphone access on localhost and have the query ready:
   `JEE Main session 1 ki registration last date kab hai?` The feature sends the
   clip to Sarvam only when Transcribe is selected. Typed search is the fallback.
7. Optional scanned-document insert: only use an already captured official PDF in
   the administrator review queue whose source and scan are suitable for a demo.
   Open **Review queue → Inspect evidence → Recover PDF text with Vision**. Show the
   recovered text beside the original source and say it needs human comparison.
   Reuse a cached OCR result if present; a new Vision request is paid and subject to
   the configured 500-credit reserve. Do not upload a fabricated notice, publish an
   unreviewed scan, or make a paid request without checking the current balance.
   NiyamPulse v2's production intake is based on monitored official sources; do not
   imply that students upload notices.
8. Start OBS Studio (or another screen recorder) and use a 1920×1080 canvas/output,
   30 fps, MP4 recording, desktop audio off unless needed, and a clear microphone.
   Record a 10-second test and play it back to confirm text is readable and speech
   is audible. Keep the browser at a stable 16:9 window size.

## Suggested 2-minute screen path and narration

| Time | On-screen path | Say |
|---|---|---|
| 0:00–0:12 | Public landing page, then **Explore exams** | “Exam dates and application changes are easy to miss across many official websites. NiyamPulse brings reviewed exam-cycle updates into one place, with the source kept visible.” |
| 0:12–0:28 | Learner: **Explore exams**; search/select JEE Main 2027 Session 1; show followed state or **My subscriptions** | “A learner follows the exam cycles they care about. Each cycle is separate, so a student can follow more than one exam without mixing their deadlines.” |
| 0:28–0:48 | Learner: **My overview** or **My subscriptions**; open the JEE exam brief | “Following late does not mean starting from zero. The learner can see already reviewed notices and important dates for this cycle, with the original source linked. Dates may pass or be superseded, so the source remains authoritative.” |
| 0:48–1:05 | Learner: **My inbox**; open the JEE update, show read state and source link/PDF | “After an administrator reviews a notice, NiyamPulse matches it to exam-cycle subscriptions and stores an in-app alert. The learner can open the captured source evidence and mark the alert read.” |
| 1:05–1:22 | Learner: **Explore exams**; record the Hindi/Hinglish query, stop, transcribe and choose **Use this search**. Show results. If mic fails, type the same query. | “A learner can ask in Hindi or Hinglish. Saaras transcribes the clip only after the learner chooses Transcribe; then deterministic search filters reviewed notices. It does not invent a date or follow an exam automatically.” |
| 1:22–1:32 | Play a short excerpt of the reviewed JEE narration; keep written text visible | “The notice can also be listened to in a generated voice. The exact reviewed wording and dates remain visible for comparison.” |
| 1:32–1:52 | Switch to administrator profile: **Operations overview → Source monitor**; show current status and last successful checks | “On the operator side, the source monitor checks configured official publishers and records fetch health. A successful poll can find no new notice; the system reports that honestly instead of simulating activity.” |
| 1:52–2:10 | Administrator: **Review queue → Inspect evidence** on the already reviewed JEE notice; show source links, evidence, extraction label and approval history. Do not click approve again. | “A discovery is not a notification yet. The operator checks the exact cycle and source evidence. Sarvam can extract and explain; deterministic checks and a human reviewer control publication.” |
| 2:10–2:20 | Optional: show a cached Vision result on a scanned source, or stay on source evidence | “For a scanned PDF, Vision can recover text, but the recovered text is compared against the source and is never approval by itself.” |
| 2:20–2:30 | Show disclaimer/footer or return to the learner notice with official link | “NiyamPulse is decision support, not an exam authority. Always verify deadlines and instructions in the linked official notice.” |

For a strict 90-second slot, omit the narration and optional OCR inserts, and shorten
the source-monitor shot. Keep the source, approval boundary, learner alert and
disclaimer.

## Edit and upload checklist

- Trim only the beginning/end and pauses; do not alter notice text, dates, monitoring
  status, counters, source evidence, or account roles.
- Add simple captions for the spoken narration. Check spelling of exam names and
  dates. Avoid adding fabricated dashboard metrics or claims such as “real-time” if
  the screen shows periodic polling.
- Watch the complete MP4 once. Confirm no password, email reset link, secret, private
  profile field, browser notification, or unrelated personal tab is visible.
- Use the final path `output/demo-video/NiyamPulse-v2-demo.mp4`; upload that file to
  the event platform. Keep the raw capture locally for retakes.

## If the demo behaves differently

- If the learner alert is already read, leave it read; do not reset production data
  just to perform the animation. Explain the persisted inbox/read state.
- If the microphone, provider, or network fails, use the typed query and state that
  voice is optional. Do not play a fabricated transcript or claim a live call worked.
- If the source worker is delayed or unavailable, show its displayed last-check and
  status. Do not force repeated requests or claim a new discovery.
- If the captured PDF preview fails, open the official source link and describe the
  capture viewer as unavailable in that run. Do not substitute a different notice.
- Never approve a notice solely to make a better recording. Any new publication
  requires source comparison and the authorized human-review checkpoint.
