# Decision: reform dates as a declared input

**Status: decided by Eleonora, 6 October 2026. In force once this record merges.**

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), accepting `PLAN.md` D5 (the reform dates).
Which of these reforms is material to the buffer is Nicholas's call (issue #1); this record fixes the list and its
dates, not their meaning.

## Why

The desired buffer is partly regulatory. These dates are public before they bind, so under the parent's
information-set rule they enter as scheduled inputs: each is admissible from its announcement, never from a date chosen
after seeing the data. The list is fixed here before Stage 2 describes anything, so no break date is picked to fit.

## The dates

| Effective | Reform | Announced | Source |
|---|---|---|---|
| 2021-03-31 | Temporary exclusion of Treasuries and reserves from the supplementary leverage ratio expires | 2021-03-19 | [Federal Reserve, 19 March 2021](https://www.federalreserve.gov/newsevents/pressreleases/bcreg20210319a.htm) |
| 2021-07-29 | Standing repo facility and FIMA repo facility; IORB replaces IOER | 2021-07-28 | [Federal Reserve, 28 July 2021](https://www.federalreserve.gov/newsevents/pressreleases/monetary20210728b.htm); the parent dates the facility from `ingest.SRF_INCEPTION` and splices IOER into IORB |
| 2023-03-12 | Bank Term Funding Program, after the March bank failures | 2023-03-12 | [Federal Reserve, 12 March 2023](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230312a.htm) |
| 2023-07-12 | Money market fund reform adopted (liquidity fees in force from October 2024) | 2023-07-12 | [SEC press release 2023-129](https://www.sec.gov/newsroom/press-releases/2023-129) |
| 2023-12-13 | Treasury clearing rule adopted (compliance dates below) | 2023-12-13 | [SEC press release 2023-247](https://www.sec.gov/news/press-release/2023-247) |
| 2026-04-01 | Enhanced supplementary leverage ratio modified for the largest banks (optional from 2026-01-01) | 2025-11-25 | [Federal Register, 1 December 2025](https://www.federalregister.gov/documents/2025/12/01/2025-21626/regulatory-capital-rule-modifications-to-the-enhanced-supplementary-leverage-ratio-standards-for-us) |
| 2026-12-31 | Mandatory clearing of eligible Treasury cash transactions | 2025-02-25 (extension) | [Federal Register, 4 March 2025](https://www.govinfo.gov/content/pkg/FR-2025-03-04/html/2025-03351.htm); reaffirmed in the [SEC statement of August 2026](https://www.sec.gov/newsroom/speeches-statements/uyeda-statement-update-secs-work-toward-treasury-clearing-implementation-080726-update-secs-work-toward-treasury-clearing-implementation-august-2026) |
| no later than 2027-01-18 | GENIUS Act effective: payment-stablecoin reserves held in bills, short repo and similar assets | 2025-07-18 (enactment) | [S. 1582, 119th Congress](https://www.congress.gov/bill/119th-congress/senate-bill/1582); effective at the earlier of 2027-01-18 or 120 days after final regulations |
| 2027-06-30 | Mandatory clearing of eligible Treasury repo transactions | 2025-02-25 (extension) | As for 2026-12-31 |

A compliance date that moves again is recorded as a new row with its own announcement date. No row is edited after
this record merges.

## Uses

- **Stage 2:** the demand curve is also split at the 2021 and 2023 reforms, reported beside the parent's regimes.
- **Stage 3:** a reform may enter as a declared shift in the buffer; decided when Stage 3 is designed.
- **Evaluation:** the reported-only reform splits in `evaluation.md`.
