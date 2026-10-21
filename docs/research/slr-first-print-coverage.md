# SLR headroom (#148): what the CDR archive holds, and whether D's first-print test can be met

**Hand-written report. Not a decision record and not an input declaration. No fit, no score.** Hypothesis and step: H7m,
groundwork G5 (candidate D). It applies Eleonora's ruling of 20 October 2026 on finding #142, option (b), and the
test that ruling sets: a first-print vintage rule for D's SLR headroom is declared only if a complete quarter of the nine
banks is readable on some day of the first episode (2018 to 2020-03-13). Otherwise D is dropped as a contender.

## 1. What the archive holds

The archive is `archive/cdr/manifest.json` on the branch `cdr-archive` (L24 and L29, PR #102 and PR #112; the copy on
`main` is the state at the last merge). It was started under Eleonora's ruling 2 of 13 October 2026 ("so that future
quarters keep their first prints"). Read from that branch on 20 October 2026:

| quarter-end | first retrieved (UTC) | stored | note |
|---|---|---|---|
| 2026-03-31 | 2026-10-14 04:20:06 | no (`not_stored`, bytes lost) | superseded in the manifest by the next row |
| 2026-03-31 | 2026-10-16 11:23:45 | yes | retrieval time is the upload time of run 38893471133 |
| 2026-06-30 | 2026-10-14 04:20:06 | no (`not_stored`, bytes lost) | superseded in the manifest by the next row |
| 2026-06-30 | 2026-10-16 11:23:43 | yes | retrieval time is the upload time of run 38893471133 |

The archive holds two quarter-ends, for every bank the bulk file carries. It holds no quarter before 2026-03-31. By
the archive's own availability rule a file is available from its `first_retrieved_utc`, never earlier
(`archive/cdr/README.md`), so the earliest first print it can serve is public from 2026-10-14, after the parent's
development end (2026-09-03).

Per bank and quarter, for the nine banks of the main measure (JPMorgan Chase Bank, N.A.; Bank of America, N.A.;
Citibank, N.A.; Wells Fargo Bank, N.A.; Goldman Sachs Bank USA; Morgan Stanley Bank, N.A.; Morgan Stanley Private Bank,
N.A.; State Street Bank and Trust Company; The Bank of New York Mellon): **no first print is held for any bank in any
quarter from 2017-03-31 to 2025-12-31.** For 2026-03-31 and 2026-06-30 the first retrieval is as in the table, the same
for every bank in a file.

## 2. Her test

- **First readable complete quarter under a first-print rule:** 2026-03-31, public from 2026-10-14 at the earliest
  (the stored copy: 2026-10-16). Whether all nine banks are in it was not checked: it does not change the answer.
- **Inside the first episode (2018 to 2020-03-13)?** No. The first episode ended more than six years before the first
  retrieval.
- **Test: not met.** This is the "history cannot be obtained" outcome of the ruling.

## 3. Why no other source closes the gap

- The CDR serves only the latest-filed figures; each bulk file is rebuilt from current content and there is no vintage
  selector (`docs/research/slr-headroom-due-diligence.md`, section 1). Its timestamps show the latest submission, not the
  first: for the nine banks the last update was 28 to 1713 days after quarter-end (`declarations/ffiec_call_slr.json`).
- The Call Report is filed by a bank in a quarter, so a first print cannot be rebuilt from a later one: an amendment
  replaces the earlier figure, and the earlier is not served.
- Not checked: any non-CDR archive of the early filings (a third-party mirror, a web archive of past bulk files). None
  is known to this repository; finding one would be a new directive, with its own declaration.

## 4. What this report does not do

No vintage rule is declared, `docs/decisions/data-meaning.md` row 16 is not amended, no `slr_headroom` first-print
snapshot is published, and no leakage or staleness test is added: each of those exists only on the "can be obtained"
branch of the ruling. The latest-filed series (row 16(d), ruling 1) is unchanged and D is not refitted. The consequence,
for her to rule on, is that D has no first-episode fit under a first-print rule, and the ruling says to drop D as a
contender; #147's calendar-clean run of D waits on that.
