# SLR headroom (#27): due diligence on first-print availability

> **Correction (15 October 2026).** The State Street lines below are for IDRSSD 93619, State Street Bank and Trust
> Company, N.A., a trust subsidiary of about $65 million, not the bank of the G-SIB (IDRSSD 35301). They are kept as
> run. The extract reads 35301 (`snapshots/SUPERSEDED.md`, 15 October 2026).

**Status: step 1 of #27, written first. It finds that the first-filed figures Nicholas's answer 16(d) asks for cannot be
recovered from any public source this repository can reach. Nothing past this step is built.** Hypothesis and step: H7m,
groundwork G5 (candidate D, `docs/stages/stage-6.md`). No score.

Answer 16 is recorded in `docs/decisions/data-meaning.md`. Read with it.

## 1. What the source serves

- **Where:** the FFIEC Central Data Repository's public bulk download, `https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx`,
  product "Call Reports -- Single Period", one zip per quarter-end (the page lists quarter-ends from 2001-03-31 to
  2026-06-30). The zip holds one tab-delimited file per schedule; Schedule RC-R Part I is `Call Schedule RCRI`.
- **The items the SLR needs**, for a bank that reports them, are in `RCRI`: tier 1 capital (item 8274) and total leverage
  exposure (item H015), in USD thousands, in a consolidated column (`RCFA...`) and a domestic-offices column
  (`RCOA...`). Which form items define the SLR numerator and denominator in each year is **not checked against the
  current FFIEC 031 instructions** (see "Not checked"): the mapping above is read from the file's own item descriptions.
- **Only the latest-filed figures are served.** The `Readme.txt` of each zip says it holds the data "as of" the date the
  file was built, and the bulk file for any past quarter-end is rebuilt from the repository's current content. There is no
  vintage selector on the page. The zips saved for this note were built "as of" 2025-06-15 (the 2018 quarter),
  2026-01-15 (the 2021 quarter) and 2026-09-15 (the 2023 and 2025 quarters).
- **What each filer's row carries about timing:** one column, "Last Date/Time Submission Updated On" in
  `Call Bulk POR`. It is the time of the **latest** submission for that quarter. It is not the time of the first filing,
  and the repository keeps no earlier one in the public files.

## 2. What the timestamps show

Produced by `scripts/diagnostics/ffiec_slr_diligence.py` on four saved quarters (SHA-256 of each zip below). "Days" is
from the quarter-end to the latest submission update.

```
== quarter ended 2018-03-31; file as of 2025-06-15T04:30:03
filers 5656; days from quarter-end to last submission update: median 27.0, max 1854; updated more than 45 days after quarter-end: 1164 (20.6%)
  JPMorgan Chase Bank, N.A. (852218): last updated 2019-10-08 17:04 (+556 days); tier 1 capital 187903000; total leverage exposure 2799403000
  Bank of America, N.A. (480228): last updated 2021-12-17 10:13 (+1357 days); tier 1 capital 147645000; total leverage exposure 2088455000
  Citibank, N.A. (476810): last updated 2020-03-25 15:28 (+725 days); tier 1 capital 128546000; total leverage exposure 1897742000
  Wells Fargo Bank, N.A. (451965): last updated 2020-05-15 09:32 (+776 days); tier 1 capital 141113000; total leverage exposure 1997633000
  Goldman Sachs Bank USA (2182786): last updated 2018-09-28 15:41 (+181 days); tier 1 capital 25895000; total leverage exposure 365153000
  Morgan Stanley Bank, N.A. (1456501): last updated 2019-10-29 19:57 (+577 days); tier 1 capital 15514000; total leverage exposure 171664000
  Morgan Stanley Private Bank, N.A. (2489805): last updated 2019-10-29 20:51 (+577 days); tier 1 capital 6382000; total leverage exposure 68298000
  State Street Bank and Trust Company, N.A. (93619): last updated 2018-04-30 13:17 (+30 days); tier 1 capital 32631; total leverage exposure blank
  The Bank of New York Mellon (541101): last updated 2019-03-05 14:20 (+339 days); tier 1 capital 20678000; total leverage exposure 300293000
== quarter ended 2021-03-31; file as of 2026-01-15T04:30:03
filers 5026; days from quarter-end to last submission update: median 28.0, max 1611; updated more than 45 days after quarter-end: 996 (19.8%)
  JPMorgan Chase Bank, N.A. (852218): last updated 2023-06-07 14:53 (+798 days); tier 1 capital 242466000; total leverage exposure 3867551000
  Bank of America, N.A. (480228): last updated 2025-08-28 09:12 (+1611 days); tier 1 capital 166685000; total leverage exposure 2574430000
  Citibank, N.A. (476810): last updated 2023-03-16 15:14 (+715 days); tier 1 capital 148487000; total leverage exposure 2170820000
  Wells Fargo Bank, N.A. (451965): last updated 2021-05-05 12:17 (+35 days); tier 1 capital 149957000; total leverage exposure 2095040000
  Goldman Sachs Bank USA (2182786): last updated 2023-08-18 16:18 (+870 days); tier 1 capital 31137000; total leverage exposure 355735000
  Morgan Stanley Bank, N.A. (1456501): last updated 2021-04-30 16:34 (+30 days); tier 1 capital 17530000; total leverage exposure 222217000
  Morgan Stanley Private Bank, N.A. (2489805): last updated 2021-04-30 16:32 (+30 days); tier 1 capital 8471000; total leverage exposure 129468000
  State Street Bank and Trust Company, N.A. (93619): last updated 2022-02-25 10:34 (+331 days); tier 1 capital 30734; total leverage exposure 40994
  The Bank of New York Mellon (541101): last updated 2021-05-05 11:02 (+35 days); tier 1 capital 22558000; total leverage exposure 273816000
== quarter ended 2023-06-30; file as of 2026-09-15T04:30:03
filers 4696; days from quarter-end to last submission update: median 28.0, max 1154; updated more than 45 days after quarter-end: 1342 (28.6%)
  JPMorgan Chase Bank, N.A. (852218): last updated 2024-12-16 15:22 (+535 days); tier 1 capital 279236000; total leverage exposure 3997113000
  Bank of America, N.A. (480228): last updated 2025-09-23 13:29 (+816 days); tier 1 capital 185255000; total leverage exposure 2871534000
  Citibank, N.A. (476810): last updated 2025-06-06 16:06 (+707 days); tier 1 capital 152612000; total leverage exposure 2162693000
  Wells Fargo Bank, N.A. (451965): last updated 2024-08-29 17:18 (+426 days); tier 1 capital 142300000; total leverage exposure 2005228000
  Goldman Sachs Bank USA (2182786): last updated 2024-07-02 14:18 (+368 days); tier 1 capital 49912000; total leverage exposure 699123000
  Morgan Stanley Bank, N.A. (1456501): last updated 2023-09-05 10:37 (+67 days); tier 1 capital 20526000; total leverage exposure 261458000
  Morgan Stanley Private Bank, N.A. (2489805): last updated 2023-07-28 18:00 (+28 days); tier 1 capital 15502000; total leverage exposure 206050000
  State Street Bank and Trust Company, N.A. (93619): last updated 2023-07-28 09:41 (+28 days); tier 1 capital 47223; total leverage exposure 46955
  The Bank of New York Mellon (541101): last updated 2024-07-10 10:19 (+376 days); tier 1 capital 20653000; total leverage exposure 251963000
== quarter ended 2025-12-31; file as of 2026-09-15T04:30:03
filers 4393; days from quarter-end to last submission update: median 29, max 257; updated more than 45 days after quarter-end: 675 (15.4%)
  JPMorgan Chase Bank, N.A. (852218): last updated 2026-06-26 17:00 (+177 days); tier 1 capital 294807000; total leverage exposure 4571728000
  Bank of America, N.A. (480228): last updated 2026-03-02 17:04 (+61 days); tier 1 capital 190831000; total leverage exposure 3101283000
  Citibank, N.A. (476810): last updated 2026-07-07 17:59 (+188 days); tier 1 capital 160338000; total leverage exposure 2374748000
  Wells Fargo Bank, N.A. (451965): last updated 2026-02-04 17:26 (+35 days); tier 1 capital 151833000; total leverage exposure 2141519000
  Goldman Sachs Bank USA (2182786): last updated 2026-02-04 14:29 (+35 days); tier 1 capital 64071000; total leverage exposure 912004000
  Morgan Stanley Bank, N.A. (1456501): last updated 2026-01-30 13:35 (+30 days); tier 1 capital 25545000; total leverage exposure 337102000
  Morgan Stanley Private Bank, N.A. (2489805): last updated 2026-01-30 13:37 (+30 days); tier 1 capital 17298000; total leverage exposure 254197000
  State Street Bank and Trust Company, N.A. (93619): last updated 2026-01-30 11:19 (+30 days); tier 1 capital 60232; total leverage exposure 59708
  The Bank of New York Mellon (541101): last updated 2026-02-04 10:39 (+35 days); tier 1 capital 22846000; total leverage exposure 298058000
```

- **Across all filers**, between 15% and 29% of banks in each of the four quarters were last updated more than 45 days
  after quarter-end, that is, after any filing deadline (30 days, 35 for some filers; answer 16(d)). The tail runs to
  1,854 days.
- **For the nine G-SIB depository subsidiaries**, the latest update is mostly months or years after the deadline: for
  the 2018, 2021 and 2023 quarters most of the nine were last updated 180 to 1,611 days after quarter-end, and even for
  the 2025-12-31 quarter two of nine (JPMorgan Chase Bank, N.A. and Citibank, N.A.) were last updated on 2026-06-26 and
  2026-07-07. So the figure in a bulk file is, for most of the banks in the main measure, an **amended** figure, not
  the first-filed one. The file does not say what the first-filed figure was, or by how much it moved.
- **A bank whose latest update falls inside the deadline window** (for example Morgan Stanley Bank, N.A. for 2021-03-31,
  +30 days) was last updated at its first filing or in the days after it. Even then the file cannot say whether a
  filing and a same-window resubmission happened; the timestamp is an upper bound on when that value was public.

## 3. What this means for answer 16(d)

Answer 16(d) asks for each quarter to be "known only from the date the first-filed data were retrievable, declared from
your own archive's timestamps", with first filings only and no revised figures. This repository has no archive of
past Call Report downloads: the saved zips above were fetched on 13 October 2026. Three readings are possible, and
choosing among them is a data-meaning question (Nicholas's) and a decision about what the published input is
(Eleonora's). None is built here.

1. **Wait and archive.** Start downloading each new quarter's bulk file on a schedule from now, so first-filed figures
   are held for later quarters. Quarters already past have no first print here. A candidate D that must be fitted on the
   2018-2026 scarce episodes then has no first-print anchor for them.
2. **Use the latest-filed figures with the latest-update time as availability.** Each (bank, quarter) value is declared
   available from its "Last Date/Time Submission Updated On" (plus the posting lag, which is also not recorded). The
   value is then a valid point-in-time record from that instant on, and earlier instants read nothing: no leakage, but
   for a bank amended long after the deadline the quarter is unavailable for months or years, and the figure read is a
   revised one, which answer 16(d) says not to use. This contradicts the answer as worded, so it needs his word.
3. **Another source of first-filed vintages** (a third-party archive, or the FFIEC's authenticated web services, which
   return per-filer submission times and the facsimile of a stated submission). Neither was tried: the web services need
   a login, and archive.org was refused by the environment's proxy (`CONNECT tunnel failed, response 403`).

**Chosen** ([Eleonora's ruling, 13 October 2026](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/44#issuecomment-6159865654),
recorded in `docs/decisions/data-meaning.md` row 16 as amending 16(d)): **reading 2 now**, the latest-filed figures as a
labelled input, available only from their latest-update time; and **reading 1 alongside it**, a scheduled archive of the
CDR bulk files, queued as #46. The ruling does not address reading 3. Nicholas has stepped back; until she names someone, Eleonora
rules on data meaning. The overlay, declaration, tests and snapshot under reading 2 wait for their own directive.

## 4. Not checked, or for Eleonora and Nicholas

- **Not checked:** item definitions against the current FFIEC 031 instructions (his caveat); the FR Y-9C (holding
  companies, a sensitivity only) and FFIEC 101 Schedule A month-end values (not fetched; the FR Y-9C is published by the
  Federal Reserve's NIC, a different host); which of the nine subsidiaries were subject to the 6% enhanced ratio in each
  quarter; each subsidiary's 2020-21 election status (answer 16(e)); the posting lag between submission and public
  availability.
- **For Nicholas (answered by Eleonora's ruling above: reading 2 accepted as a labelled input):** is reading (2) acceptable as a labelled sensitivity, or must the input wait for archived first prints
  (reading 1)? Is there a source of Call Report first-filed vintages he knows of?
- **For Eleonora (answered by her ruling above: yes, as #46):** a decision whether this repository starts a scheduled archive of the CDR bulk files (reading 1), which
  adds a recurring fetch and a new snapshot series.

## Checksums

```
a9be30d444f7a2dd4d43db96d2a8bc56eb8deac28387617b7bcb46482742f87c  FFIEC CDR Call Bulk All Schedules 03312018.zip
92bc2920c195dfb1ad0f3e6014d7aca9c82c01184fa1da83b69643dabd150ce1  FFIEC CDR Call Bulk All Schedules 03312021.zip
49c6c8e6f5a7df28f102b25d8ca4e61616fb89eefba595e98c179b5cbd5800f0  FFIEC CDR Call Bulk All Schedules 06302023.zip
66d9881a82c4e7391acfe7b75fa2ada5c6fcbd8fb8325a71025b50fd62db6097  FFIEC CDR Call Bulk All Schedules 12312025.zip
```

The zips are not tracked (about 6 to 8 MB each, as for the H.8 and H.4.1 pages).

## How to reproduce

Fetch the four quarters from the bulk page (select "Call Reports -- Single Period", the quarter-end, "Tab Delimited"),
save the zips in one directory, then:

```
python3 -I scripts/diagnostics/ffiec_slr_diligence.py DIRECTORY
```

The files are rebuilt from the repository's current content, so a later fetch of the same quarter gives later "as of"
dates and possibly different latest-update times; that is the finding.
