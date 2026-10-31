# Observed source verification — 30 October 2026

These are genuine direct HTTP runs of the implemented adapters, not search-result
claims or mocked test passes. Source matching does not certify authenticity.

| Publisher | Listing | Native check time (UTC) | Observed outcome |
|---|---|---|---|
| National Testing Agency | [JEE Main public notices](https://jeemain.nta.nic.in/public-notices/) | 2026-10-30 17:36:49 | HTTP 200, one link mapped to JEE Main 2027 Session 1, actual PDF downloaded/extracted, one NEEDS_REVIEW notice |
| Union Public Service Commission | [Active examinations](https://www.upsc.gov.in/examinations/active-exams) | 2026-10-30 17:36:55 | HTTP 200, five recognized links, ESE 2027 detail page downloaded/extracted, four older cycles left unmapped, one NEEDS_REVIEW notice |

Both adapters were enabled in the local database after these successful checks;
checked-in source defaults remain disabled. Polling is hourly and independent of
the frontend. Neither genuine notice was auto-approved or dispatched during QA.

## Exact stored byte hashes

- NTA listing, 84,905 bytes:
  `219d085ec6c1b3c548edf71ddb0dea7000dc402c31de4dfc0ae5fe76065e0d22`
- Observed NTA S3WaaS PDF, 1,445,439 bytes:
  `e5670a67f36b643918aa5012459968a8113581f669923242a87845c9b8d38ae5`
- UPSC listing, 37,780 bytes:
  `53c9dc0b816d4139ac8a73fa7a5ecedb9c3a07f92fd1225210903944354e4224`
- UPSC ESE 2027 detail page, 30,217 bytes:
  `bb3dcce27cfcb8f8925913ab719d006eb24b87a959035fd6fa09d7f75aa5d76f`

The earlier adapter-test captures in `tests/fixtures/official/` have their own
manifest and timestamps. UPSC's visitor counter changed the raw listing hash
between captures; this must not invent another substantive notice. Raw bytes
remain immutable, while dedup uses exact cycle/title/version and extracted content.

## Robots and site-use checks

- NTA robots returned HTTP 200 and allowed the public listing path. Its actual
  observed PDF host `cdnbbsr.s3waas.gov.in` was added as an exact allowlist entry;
  arbitrary external PDF hosts are not trusted.
- UPSC robots returned 302 to the same-host homepage, followed by HTML without
  robot directives. Health records `ROBOTS_REDIRECTS_TO_HOME_NO_DIRECTIVES`.
  This nonstandard response is not presented as publisher permission.
- [NTA terms](https://jeemain.nta.nic.in/terms-and-conditions/) and
  [UPSC website policy](https://www.upsc.gov.in/website-policy) were read via HTTP
  200. UPSC permits direct links and disallows framing; the UI opens original
  notices in a separate tab and does not embed the website. Its reproduction
  permission language must be reviewed before public content syndication.
- This is a localhost prototype with private evidence captures and synthetic
  recipients. No public deployment or publisher endorsement is claimed.

No CAPTCHA, protection bypass, guessed private API or application submission was
used. The GATE source remains disabled; its kit-supplied year-specific URL did not
successfully verify in this run. NEET, SSC and further adapters remain untested.

## Current coverage boundary

NTA: the configured listing and linked PDFs, mapped by explicit year/session.
UPSC: the active-exam listing and mapped exam-detail HTML pages. Deep attachment
content changes, archive pagination and broad all-exam coverage are not implemented.
Each poll is capped at five mapped documents. Review is required for publication.


## 31 October 2026 extension

NTA NEET UG was independently fetched with robots allowed; its observed S3WaaS
PDF host is now allowlisted. Ten notices route explicitly to NEET UG 2026
post-exam coverage, distinct from 2027. Actual second-batch polling proved tail
rotation. UPSC attachment ancestry was exercised against the actual 62-page ESE
bulletin. Source facts, limits, costs, hashes and observed outcomes are recorded
in [PHASES_1_3_REPORT.md](history/PHASES_1_3_REPORT.md); offline capture hashes are in
`tests/fixtures/official/capture_manifest.json`. Config defaults remain disabled
until a fresh runtime completes its own check. No cryptographic authenticity claim.
