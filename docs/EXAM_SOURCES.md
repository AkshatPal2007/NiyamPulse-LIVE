> **Implementation update:** NTA JEE Main and UPSC active-exam adapters have now
> completed actual native checks and are enabled in the local runtime database.
> Checked-in defaults remain disabled. See `SOURCE_VERIFICATION.md` for proof and
> boundaries. The GATE URL below is a kit-supplied candidate that did not verify
> successfully in this run; do not treat it as active or confirmed coverage.

# Exam coverage and official-source registry — research snapshot

**Checked 2026-10-30.** "Listing verified" means an official-site announcement page was located, NOT that a crawler works, the notice is cryptographically authenticated, or every exam/year is being watched. Live adapters remain **disabled** in `config/source_registry.json` until implemented and exercised. This is a configurable starting point, not blanket coverage.

## Audience and launch catalog

| Segment | Exam / programs | Priority | Catalog vs active watcher |
|---|---|---|---|
| Class 11/12 / school leavers | **JEE Main**, **NEET UG**, **NDA/NA** | A | catalog now; implement monitored sources |
| School / engineering entrance | JEE Advanced, CUET UG, BITSAT, VITEEE, state CETs | B | catalog/roadmap; source adapters pending |
| Engineering undergraduates / graduates | **GATE**, **UPSC Engineering Services (ESE)**, **SSC Junior Engineer (JE)** | A | catalog now; monitor source by cycle |
| Engineering opportunities | RRB JE, ISRO Scientist/Engineer, DRDO Scientist B, PSU recruitment via GATE | B | prospective; coverage depends on verified recruiters and notices |
| General public exams also relevant | SSC CGL, SSC CHSL | B | catalog and shared SSC source; NOT product's sole focus |

**A single source can cover multiple exams.** For example, UPSC active examinations can include NDA and ESE. Routing to the correct `cycle_id`, including year/session/phase, is mandatory; do not notify everybody following the organizer.

## Official pages verified as public listings

| Source ID | Publisher / relevant exams | Observed public page | Verification | Next engineering test |
|---|---|---|---|---|
| `nta-jee-main` | NTA · JEE Main | https://jeemain.nta.nic.in/public-notices/ | Official listings observed | Test HTML parse, pagination and PDF links |
| `nta-neet-ug` | NTA · NEET UG | https://neet.nta.nic.in/public-notices/ | Official listings observed | Test HTML parse and file redirects |
| `upsc-active` | UPSC · NDA, ESE | https://www.upsc.gov.in/examinations/active-exams | Official active-exams listing observed | Test exam title matching, outgoing links, date parsing |
| `ssc-board` | SSC · JE, CGL, CHSL | https://ssc.gov.in/ | Official notice board observed | Test client-side rendering, API/network requests if allowed, dedup |
| `gate-2027` | IIT Madras · GATE 2027 | https://gate2027.iitm.ac.in/notifications | Official year-specific notifications observed | Test page parsing & link/diff extraction |

Citation / verification links for human review:
- JEE Main official notices: https://jeemain.nta.nic.in/public-notices/
- NEET UG official notices: https://neet.nta.nic.in/public-notices/
- UPSC active examinations: https://www.upsc.gov.in/examinations/active-exams
- UPSC ESE 2027 example: https://www.upsc.gov.in/examinations/Engineering%20Services%20%28Preliminary%29%20Examination%2C%202027
- SSC official notice board: https://ssc.gov.in/
- GATE 2027 official notifications: https://gate2027.iitm.ac.in/notifications

**No stable public RSS/API or permission to scrape has been verified.** Before implementing any adapter, inspect robots.txt/site terms, rate-limit, use appropriate user-agent, honor caching, cap downloads, and do not bypass access controls or CAPTCHAs. Only fetch explicit allowlisted hosts, and validate redirects/URLs against SSRF.

## Delivery rollout

1. **Source #1:** NTA JEE Main. Test genuine listing discovery and dedup; this also gives a realistic school-student experience.
2. **Source #2:** GATE 2027 OR UPSC active examinations (different publisher). Demonstrate generality across education stages.
3. Add NTA NEET UG, UPSC NDA/ESE and SSC JE with separate fixtures, routing and error handling.
4. Expand catalog coverage to JEE Advanced, CUET UG, BITSAT, VITEEE, state CETs, RRB JE and technical recruiting bodies only after sources are verified and adapters tested. Distinguish `CATALOG_ONLY`, `SOURCE_CONFIGURED`, and `LIVE_MONITORED` prominently on user UI.

## Practical content categories

The watcher covers **all relevant notices**, not only eligibility-rule amendments: application registration/open/close, extension, exam dates, city/admit card information, answer-key/challenge windows, syllabus corrections and results. Each can be sent as a general exam update to subscribers after review. **Only five closed-set rule types** may produce deterministic eligibility status changes.

## Demo trust policy

Use synthetic notices & user profiles for deterministic cohort testing. Display `SYNTHETIC DEMO`, even if the notice titles resemble real exams. For a truly live URL, preserve its official page and downloaded file hash. Never invent an official notice, a deadline, a sign-up link or an actual population count.
