# Decision: reform dates as a declared input

**Status: a DRAFT for Eleonora, not in force.** Proposed by the orchestrating session on 6 October 2026. Which reforms
are material to the buffer is Nicholas's call (issue #1); whether they enter the project is Eleonora's.

## Why

The desired buffer is partly regulatory. These dates are public before they bind, so under the parent's
information-set rule they can enter as scheduled inputs: each date is admissible from its announcement, never from a
date chosen after seeing the data. Fixing the list here, before Stage 2 describes anything, keeps break dates from being
picked to fit.

## The dates

| Effective | Reform | Announced | Source |
|---|---|---|---|
| 2021-03-31 | Temporary exclusion of Treasuries and reserves from the supplementary leverage ratio expires | 2021-03-19 | Federal Reserve press release, 19 March 2021 (to be attached) |
| 2021-07-29 | Standing repo facility and FIMA repo facility begin; IORB replaces IOER | 2021-07-28 | FOMC statement and implementation note, 28 July 2021 (to be attached); the parent already dates the facility from `ingest.SRF_INCEPTION` and splices IOER into IORB |
| 2023-03-12 | Bank Term Funding Program, after the March bank failures | 2023-03-12 | Federal Reserve press release, 12 March 2023 (to be attached) |
| 2023-07-12 | Money market fund reform adopted; liquidity fees in force from October 2024 | 2023-07-12 | SEC release, 12 July 2023 (to be attached) |
| 2023-12-13 | Treasury clearing rule adopted (phased compliance below) | 2023-12-13 | SEC release, 13 December 2023 (to be attached) |
| 2026-04-01 | Enhanced supplementary leverage ratio modified for the largest banks (optional from 2026-01-01) | 2025-11-25 | [Federal Register, 1 December 2025](https://www.federalregister.gov/documents/2025/12/01/2025-21626/regulatory-capital-rule-modifications-to-the-enhanced-supplementary-leverage-ratio-standards-for-us) |
| 2026-12-31 | Mandatory clearing of eligible Treasury cash transactions | 2025-02-25 (extension) | [Federal Register, 4 March 2025](https://www.govinfo.gov/content/pkg/FR-2025-03-04/html/2025-03351.htm); reaffirmed in the [SEC statement of August 2026](https://www.sec.gov/newsroom/speeches-statements/uyeda-statement-update-secs-work-toward-treasury-clearing-implementation-080726-update-secs-work-toward-treasury-clearing-implementation-august-2026) |
| no later than 2027-01-18 | GENIUS Act effective: stablecoin reserves held in bills, short repo and the like | 2025-07-18 (enactment) | Statute; the exact date depends on final regulations (to be attached) |
| 2027-06-30 | Mandatory clearing of eligible Treasury repo transactions | 2025-02-25 (extension) | As for 2026-12-31 |

A row marked "to be attached" gets its primary source before this record is decided. A compliance date that moves
again is recorded as a new row with its own announcement date; no row is edited after it is decided.

## Proposed uses

- **Stage 2:** the demand curve is also split at the 2021 and 2023 reforms, as a reported sensitivity beside the
  parent's regimes.
- **Stage 3:** a reform may enter as a declared shift in the buffer; decided when Stage 3 is designed.
- **Evaluation:** see `evaluation-amendment-reform-splits.md`.
