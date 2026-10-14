# The SLR requirement, by period: DRAFT

**Status: DRAFT, for Eleonora to review and merge (#71, her decision on #69, Q1). Nothing here is in force until she merges it.**
`src/repo_liquidity/slr.py` reads the table below (`REQUIREMENT_TABLE`); `tests/test_slr.py` (`RequirementTableTests`) checks
that the table in the code and this record agree.

## What the table is for

`docs/decisions/data-meaning.md` row 16 defines the headroom of a G-SIB depository subsidiary as its supplementary leverage
ratio (SLR) minus the requirement in force on the quarter-end. This record fixes that requirement, period by period, from the
rule text. The headroom of a quarter with no value in the table is **blank**, never a guess.

## The table

| Period (quarter-ends) | Requirement | Rule |
|---|---|---|
| 2018-01-01 to 2026-03-31 | **6.0%** | 12 CFR 6.4(c)(1)(iv)(B), as added at 79 FR 24539 (May 1, 2014) |
| 2026-04-01 on | **none in the table: bank-specific** (open question 1) | 12 CFR 3.10(a)(1)(v) and 3.11(c)(2)(v), as amended at 90 FR 55287 and 55288 (Dec. 1, 2025) |

Quarter-ends before 2018-01-01 have no entry: the 6% standard applied "on January 1, 2018, and thereafter".

### 2018-01-01 to 2026-03-31: 6.0%

The rule is the prompt corrective action standard for a "well capitalized" national bank or Federal savings association
(OCC, 12 CFR part 6). The text in the eCFR as of 2018-01-01, paragraph (c)(1)(iv)(B) of section 6.4, reads:

> (B) With respect to a national bank or Federal savings association that is a subsidiary of a U.S. top-tier bank holding
> company that has more than $700 billion in total assets as reported on the company's most recent Consolidated Financial
> Statement for Bank Holding Companies (FR Y-9C) or more than $10 trillion in assets under custody as reported on the
> company's most recent Banking Organization Systemic Risk Report (Y-15), on Jan. 1, 2018 and thereafter, the national bank
> or Federal savings association has a supplementary leverage ratio of 6.0 percent or greater

The text in the eCFR as of 2026-03-31, section 6.4(b)(1)(i)(D)(2), is the same standard, with the reporting-form name updated
("Form FR Y-9C", "Form FR Y-15") and "January 1, 2018, and thereafter". The source credit of the 2018 text is
`[78 FR 62275, Oct. 11, 2013, as amended at 79 FR 24539, May 1, 2014]`; the 2026-03-31 text adds amendments at 84 FR 61794
(Nov. 13, 2019), 85 FR 10968 (Feb. 26, 2020), 85 FR 32989 (June 1, 2020) and 88 FR 89842 (Dec. 28, 2023), none of which
changes the 6.0 percent figure in the text read at 2026-03-31.

*Transition or early adoption:* none is stated in these paragraphs. The temporary exclusion of reserves and Treasuries (April
2020 to March 2021) changes the **measure**, not this requirement; it is recorded per bank-quarter as "exclusion status
unknown" (data-meaning row 16(e)).

### From 2026-04-01

The eCFR version of 12 CFR 6.4 dated 2026-04-01 (source credit `90 FR 55288, Dec. 1, 2025`) no longer contains the SLR
condition for a well capitalized bank: paragraph (b)(1)(i)(D) now reads only "(D) Leverage Measure: The national bank or
Federal savings association has a leverage ratio of 5.0 percent or greater". The standard moved to the capital-buffer
rule. 12 CFR 3.10(a)(1)(v) sets the minimum:

> (v) For advanced approaches national banks or Federal savings associations or, for Category III OCC-regulated institutions,
> a supplementary leverage ratio of 3 percent.

and 12 CFR 3.11(c)(2)(v), "Leverage buffer standard", sets a buffer on top of it:

> For a national bank or Federal savings association that is a subsidiary of a U.S. top-tier bank holding company that has
> more than $700 billion in total assets as reported on the company's most recent Consolidated Financial Statement for Bank
> Holding Companies (Form FR Y-9C) or more than $10 trillion in assets under custody as reported on the company's most recent
> Banking Organization Systemic Risk Report (Form FR Y-15), the leverage buffer standard is equal to the lesser of 1.0 percent
> or, if applicable, 50 percent of the most recent method 1 surcharge (expressed as a percentage) that the global
> systemically important BHC that controls the national bank or Federal savings association was required to calculate
> pursuant to § 217.403(b), subject to the effective date provisions of § 217.403(d).

A bank's SLR minus 3 percent is its "leverage buffer" (3.11(c)(2)(ii)); falling below the buffer standard limits
distributions (3.11(c)(1), table 2). It is a payout limit, not a prompt corrective action threshold. The old text of section
3.11 (as of 2026-03-31) has no SLR buffer for these subsidiaries.

**The table gives no value from 2026-04-01.** The standard is `3% + min(1.0%, 50% x the parent's method 1 surcharge)`, and the
surcharge is each parent's own number, so the headroom of those quarters stays blank until she decides (open question 1).

## Open questions for Eleonora

Not settled in code; the table above leaves each open as stated.

1. **Which requirement from 2026-04-01?** Options the text supports: (a) leave the headroom blank (the table as drafted);
   (b) the common floor, 3.0%, 3.10(a)(1)(v), a requirement every bank meets; (c) 3% plus the leverage buffer standard,
   `3% + min(1.0%, 0.5 x surcharge)`, bank by bank. Under (c) the value depends on each parent's method 1 surcharge as most
   recently required by 12 CFR 217.403(b) (read from the parent's FR Y-15, or from the Federal Reserve's published
   surcharges); this record fetched no surcharge. Quarters ending 2026-03-31 are before the date and take 6.0%; the first
   affected quarter-end is 2026-06-30. The extract holds those rows: one per bank, with no headroom.
2. **Is the 6% line the right "requirement" for the earlier period?** Row 16(b) of data-meaning says so ("the 6% enhanced
   ratio at G-SIB subsidiaries was the stricter constraint"). The text above confirms 6.0% as the *well capitalized* level.
   The legal minimum in the same period was 3% (12 CFR 3.10(a)(1)(v)) and was never the binding one.
3. **Other primary regulators.** Only the OCC's text (12 CFR parts 3 and 6) was read. A subsidiary supervised by the Federal
   Reserve (12 CFR 208.43 and part 217) or the FDIC (12 CFR part 324) is under a parallel rule that was not fetched. The
   extract does not record each bank's primary federal regulator, so the table assumes the OCC text applies to all.
4. **The early-adoption window.** The 2025 final rule's effective date of 2026-04-01 is the date of the eCFR version read;
   whether a bank adopted it earlier, and so from which quarter-end its requirement differs, was not checked.
5. **Intermediate versions.** The text was read at 2018-01-01 and 2026-03-31 (and 2026-10-01). The versions dated 2019-11-13,
   2020-01-01, 2020-02-26, 2020-06-01, 2023-12-28, 2024-04-01 and 2025-12-01 were not read one by one; the 2026-03-31 text
   carries the same 6.0 percent figure, and its source credit lists the amendments between.

## Sources

Fetched 14 October 2026 from the eCFR versioner (`https://www.ecfr.gov/api/versioner/v1/full/<date>/title-12.xml`, part 6
section 6.4 as of 2018-01-01, 2026-03-31 and 2026-10-01; part 3 sections 3.10 and 3.11 as of 2026-10-01 and, for 3.11,
2026-03-31). federalregister.gov was not reachable from this environment, so the Federal Register pages themselves were
not read; the citations are the source credits the eCFR prints.
