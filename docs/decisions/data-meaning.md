# Decision: data meaning for Phase 3, questions 1 to 17

**Status: decided by Nicholas Beroud, 6 October 2026, on issue #1** ([his answer](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/1#issuecomment-6020655371)).
In force once this record merges. Under the parent's `PLAN.md` the choice of data and its meaning are his. Where he
corrects Eleonora's preliminary answers (`data-meaning-preliminary.md`, questions 1 to 5), his answer replaces hers,
as she asked. This record summarizes him. His comment on issue #1 is the authority, and wins where they differ.

## His answers

| # | Question | Answer |
|---|---|---|
| 1 | QE/QT measure | **Correction: the realized weekly change includes MBS as well as Treasuries.** MBS ran off well below its cap through 2022 to 2025 because prepayments nearly stopped, so caps overstate the MBS drain and only the realized change shows it. The level of holdings is not used. The caps (Treasury and MBS separately) are the expected pace. |
| 2 | Proxies | Agreed: H.8 total assets (first prints) for size. **The distance from SOFR to the facility's rate is the input; facility take-up is something the model observes and should explain** (see 13). |
| 3 | Caps | Agreed: known from the announcement, applied from the stated effective date, read as a maximum pace. |
| 4 | ON RRP source | Agreed: the NY Fed operation results (`nyfed_on_rrp`). |
| 5 | Facility usage before 2021-07-29 | **Correction: neither zero nor missing throughout.** From 2019-09-17 until the standing facility, the Fed's daily repo operations count as take-up, marked as a different facility. Before 2019-09-17 it is a structural zero. The distance to the ceiling is missing before July 2021. |
| 6 | Bank-size split | **Keep the run:** H.8 cash assets of large domestic, small domestic and foreign-related institutions, all three. |
| 7 | Indicator families | **Start narrow.** First, pricing (SOFR − IORB, TGCR and BGCR, percentile dispersion, SOFR − EFFR) and the Fed's facilities (ON RRP, the standing facility, SOMA flows, the TGA). Second, dealer intermediation and cash supply and demand. Last, segment distribution, because of vintage issues. |
| 8 | Specials | DVP − BGCR and SOFR's 1st percentile are acceptable but noisy proxies. SOMA securities lending and FR 2004 fails are good collateral-scarcity measures. Collateral scarcity stays on its own axis, apart from cash scarcity. |
| 9 | Basis-trade demand | Yes: CFTC TFF leveraged-fund Treasury positions, released Friday for Tuesday positions (declare that lag). They are net positions, so broader than the basis trade alone. |
| 10 | Haircuts | No reliable point-in-time public source he knows of. OFR's bilateral repo collection is the place to check. It does not block Stage 1. |
| 11 | Reforms | **The SLR exclusion ending (2021-03-31) is the most material to banks' desired reserves.** The SRF and IORB change (2021-07-29) matters much less: banks do not treat the facility as a substitute for their own reserves. The others are second-order, though the BTFP marks precautionary hoarding after SVB. **Mandatory repo clearing (2027-06-30) is a measurement break in SOFR volume and dispersion.** |
| 12 | ON RRP take-up | **Use the rate gap, not the level: TGCR minus the ON RRP rate.** Near zero, cash is abundant and parked at the Fed; well above, money funds lend in the market and the buffer is gone. Take-up stays only as the "buffer present or gone" flag (parent #232). |
| 13 | Facility take-up | **Material use at $1bn or more, fixed in advance, as an event the model should explain.** Small take-ups are operational test trades. The amount is not modelled. The continuous input stays the distance from SOFR to the facility's rate. |
| 14 | 2019–21 term repos (asked 6 October 2026; [his answer](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/1#issuecomment-6021810713)) | **Option (c), with one addition.** Take-up counts each term repo as an amount outstanding from settlement to maturity, because its cash stays in the system for its term. The material-use event ($1bn or more) counts each operation on its operation date, overnight and term alike, because that is when the demand showed. **Caveat:** in 2019–20 the Fed set the term offering sizes, partly to cover year-end, so take-up reflects the Fed's design as well as market demand. The two May 2019 tests stay out. |
| 15 | Agency debt (answered 7 October 2026, recorded 13 October 2026 for #30; [his answer](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/1#issuecomment-6040855434), reaffirmed in [his reply of 12 October](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/1#issuecomment-6131896290)) | **Include it, and call the measure "agency securities".** In his words: "The Fed's caps and its reinvestment into bills apply to agency debt and agency MBS together, so the realized change should match that definition. Agency debt is about $2.3bn on the latest H.4.1, so it won't move any result, and it reads from the same table." The measure is the H.4.1 table 1 weekly change in "Federal agency debt securities" plus that in "Mortgage-backed securities", from the same release (`repo_liquidity.h41.agency_securities`; `snapshots/agency_securities/`). The existing MBS and Treasury series are unchanged. |
| 16 | SLR headroom (asked 7 October 2026; [his answer](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/1#issuecomment-6131896290), 12 October 2026; recorded 13 October 2026 for #27) | **(a) Source:** holding companies, FR Y-9C Schedule HC-R Part I; bank subsidiaries, the Call Report (FFIEC 031) Schedule RC-R Part I; detail, FFIEC 101 Schedule A for advanced-approaches firms, which reports "month-end values for each month of the quarter". "Item numbers have moved between form versions, so take them from the current instructions, not from older drafts." **(b) Level: the depository subsidiaries**, "where reserve balances are actually held"; before 2026-04-01 the 6% enhanced ratio at G-SIB subsidiaries was the stricter constraint; holding-company headroom is "a useful sensitivity check". **(c) Banks:** the G-SIBs' subsidiaries are the main measure; Category II-III firms (3% SLR) are "a second group, not in the main measure". **(d) Timing:** "treat each quarter as known only from the date the first-filed data were retrievable, declared from your own archive's timestamps. Don't use the latest revised figures." Call Reports are due about 30 days after quarter-end (35 for some filers), the FR Y-9C about 40 (45 at year-end). **(e) The 2020-21 exclusion:** "use headroom as reported". Holding companies had it automatically (April 2020 to March 2021); subsidiaries had to elect it. "Record each subsidiary's election status if it can be found. If it can't, flag subsidiary headroom for that window as 'exclusion status unknown' rather than recomputing it." A recomputed "as if reserves had counted" series is a labelled sensitivity, never the input. **(f) Foreign-related institutions:** a separate group with no SLR anchor, tied to "the spread between IORB and their funding cost" or a free parameter; a modelling choice for candidate D's directive, recorded here and not built. **Status of (d) in practice:** see `docs/research/slr-headroom-due-diligence.md` (#27): the public CDR bulk files carry only the latest-filed figures, so (d) as worded cannot yet be met from a public archive. **(d) amended by Eleonora's ruling, 13 Oct 2026** ([her ruling](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/44#issuecomment-6159865654); Nicholas has stepped back, and until she names someone she rules on data meaning). The quote of (d) above is his answer as given and is kept unchanged; the ruling governs where they differ. **Ruling 1 (reading 2 of the due-diligence note):** the latest-filed Call Report figures are used as a labelled input, each (bank, quarter) value available only from its latest-update time. **Ruling 2 (reading 1):** this repository starts a scheduled archive of the CDR bulk files, so that future quarters keep their first prints; it runs alongside reading 2 and does not replace it (#46). **(b), (d) and the group, decided by Eleonora on #69 (14 October 2026, [her comment](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/69#issuecomment-6175564687), recorded for #71):** the requirement behind the headroom is a per-period table (`docs/decisions/slr-requirement.md`, a draft until she merges it); State Street Bank and Trust Company is excluded from the main measure and kept as a labelled sensitivity (`measure` column of the snapshot); and **the day-after rule is accepted:** a figure is read from the start of the day after its latest-update date, New York time, because the update time carries no time zone and the posting lag is not recorded, so the whole day is skipped (later than the truth, the safe side). |
| 17 | H.8 group cash assets as a stand-in for group reserves (asked 12 October 2026; [his answer](https://github.com/eleonorabjornberg/repo-market-liquidity/issues/1#issuecomment-6131896290), recorded by #26) | **(a) It works for some groups, not equally for all.** "Large domestic banks and foreign-related institutions: reserve balances are the dominant part, so cash assets are a reasonable stand-in." "Small domestic banks: vault cash and balances held at correspondent banks are a much larger share, so cash assets overstate their reserves." And "balances due from other depository institutions are another bank's liability, so they double-count relative to aggregate reserves": do not sum the groups naively. **(b) Scale, and check against an exact source quarterly.** Weekly: "scale the group shares so they sum to H.4.1 reserve balances, but keep a residual 'other depository institutions' group", because H.8 covers commercial banks only. Quarterly: check the shares against "balances due from Federal Reserve Banks" (Call Report, Schedule RC-A, for domestic banks; the corresponding item of the FFIEC 002 for foreign branches). "Use the quarterly split as the anchor, and the weekly H.8 movements to interpolate between quarters, as of each first release." **(c) Breaks to declare, each as a dated event:** the large-bank panel (the top 25 by domestic assets), reassessed at each benchmark to the Call Reports, with an immediate replacement on a merger or a departure; "the Fed adjusts past large/small levels" for mergers and panel shifts, "so revised history and first prints differ", which is another reason to read first prints; and the 2023 failures and acquisitions (SVB, Signature, First Republic), which "moved assets between groups". Source: "the H.8 release notes around each benchmark". His caveat: "Report and line references should be confirmed against the current form instructions before they're declared." |
| 18 | Group reserves: the anchor and the weekly series (Eleonora's rulings of 14 October 2026 on PR #50, for #43; **drafted in that PR for her to merge, not in force until she does**) | **(a) Foreign-related institutions** ([her ruling](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/50#issuecomment-6176272313), option (a)): "Use the H.8 foreign-related institutions' cash assets (weekly first prints, already in the repo from #42) as the foreign group's anchor, labelled an approximation (cash assets, not reserves alone). No FFIEC 002 for now; a hand-downloaded FFIEC 002 may be added later as a sensitivity check." **(b) Domestic split** ([her ruling](https://github.com/eleonorabjornberg/repo-market-liquidity/pull/50#issuecomment-6178605509), option (i)): "use the H.8 group cash shares for the domestic split as well, unanchored and labelled as an approximation, just as her earlier ruling (a) does for the foreign-related split. Do not anchor on latest-filed RC-A, because that would break rule 16(d). Do not pause candidate C. When the FFIEC CDR archive (#49) has first prints, an anchored version can be a later directive." **(c) The weekly series** (`repo_liquidity.group_reserves`): the large domestic, small domestic and foreign-related levels are each the H.8 group's cash assets, first print, labelled an approximation (`domestic_basis`, `foreign_basis`); the residual "other depository institutions" is H.4.1 reserve balances less the three, not clipped and flagged when negative. An H.8 break week is flagged (`h8_break_week`), not refused, because a level is a first print and not a ratio. **(d) The RC-A anchor** (`repo_liquidity.rca`, snapshot `snapshots/rca_anchor/`) stays as a published input but the weekly series does not read it: the 25 filers with the largest total assets (`RCFD2170`, else `RCON2170`) stand in for the Board's panel (her Q3), latest-filed figures each available only from its latest-update time and a group's sum from its slowest member's (answer 16(d) as amended). **Marked questions, not settled in code** (each is in PR #50): **(i)** the reading of "group cash shares" built here is the group's cash-asset level, not a share of reserves; **(ii)** the residual is negative in most weeks (the three groups' cash assets exceed reserves, answer 17(a)), so whether the weekly series should be published, and in what form, is hers; **(iii)** whether the RC-A anchor snapshot stays published while nothing reads it. The small-domestic caveat of answer 17(a) (cash assets overstate small banks' reserves) is carried in `docs/stages/group-reserves.md` and the series' manifest. |

## Ownership: the MBS scenario (Eleonora, 6 October 2026)

**Nicholas owns the MBS "clog" scenario**, as he asked: the balance sheet's MBS runoff and reinvestment, and the tail
case of active MBS sales draining reserves and hitting mortgage and mREIT repo funding. Its narrative, its data meaning
and its scenarios are his. The realized MBS change (answer 1) is the input it builds on.

## Checked against our sources (6 October 2026)

- **Question 1, the reinvestment regime: confirmed.** The FOMC implementation note of 29 October 2025 says: "Beginning on
  December 1, reinvest all principal payments from the Federal Reserve's holdings of agency securities into Treasury
  bills". The note of 10 December 2025 repeats it. Both are tracked under `tests/fixtures/snapshots/fomc_notes/pages/`.
  So since 1 December 2025, MBS paydowns are a composition shift from MBS into bills, neutral for reserves.
- **Question 1, the source:** H.4.1 table 1 carries a "Mortgage-backed securities" row in the same layout as the Treasury
  row, so the same archived releases give the realized MBS change.
- **Question 5, the 2019 to 2021 repo operations: checked.** The NY Fed's operation results (the endpoint of the parent's
  `nyfed_srf`) show the Desk's repo operations from 2019-09-17, overnight and term, through 2020 into 2021, until
  2021-07-28. The two repo operations of May 2019 ($65m each) were tests. Saved under
  `tests/fixtures/snapshots/nyfed_temp_repo/`. Term repos count as an amount outstanding over their term (answer 14).

## What this changes (each is a later piece of work, planned before it is built)

- **Stage 1a, corrected inputs:**
  - add the realized weekly MBS change from H.4.1 beside the Treasury change;
  - add the Fed's 2019 to 2021 repo operations as take-up from a different facility;
  - make the pre-September 2019 take-up a structural zero;
  - add the facility's material-use event ($1bn or more).
- **Stage 1b, first wave:** pricing and the Fed's facilities, as in answer 7. This includes TGCR − ON RRP rate (answer
  12), which overlaps with Stage 3b's corridor position (SOFR − ON RRP rate, over the corridor's width). Whether it
  enters as its own head is a modelling question, raised when it is planned. Then the H.8 bank-size split (answer 6) and
  the CFTC positions with their declared lag (answer 9).
- **Reform dates (answer 11):**
  - his ranking is a reading of materiality, not a change to the list in `reform-dates.md`;
  - Stage 3b already reports jumps at the legal breaks only (2021-03-31, 2023-03-12) as a sensitivity;
  - his view of the 2021 facility change applies by the same reasoning to the facility's move to a fixed rate on
    2025-12-11, which he has not addressed directly;
  - mandatory repo clearing becomes a declared measurement break for the dispersion head in the live filter.
- **Stage 3b is not changed by these answers.** It already leaves ON RRP and facility take-up out of the state.

## Note for Eleonora and Nicholas: the deleted `fed_repo` against the parent's `fed_liquidity` (12 October 2026)

**Status: a note, flagged for Eleonora and Nicholas. It decides nothing.** Written by L0 (#21), which deleted this
repository's `fed_repo.py` in favour of repo-market-model's `repo_model.fed_liquidity`
(`docs/decisions/deleted-duplicates.md`). Compared at repo-market-model `490f23d4`, over panel version 3's 2,104 dates
(2018-04-03 to 2026-09-03), `fed_repo`'s columns against `fed_liquidity.assemble`'s on the same rows. The answers
above are unchanged; where the parent's module does not carry one of them, the work that needs it must ask for it.

- **Answer 5, the structural zero before 2019-09-17: not carried.** The parent reads every date with no operation as
  zero take-up, with no facility marker, and it counts six small operations before 2019-09-17 as take-up: 2018-05-09,
  2018-05-16, 2018-11-15, 2018-12-04, 2019-05-08 and 2019-05-13, $64m to $66m each. They are not marked as small-value
  exercises in the Desk's notes. Answer 14 keeps "the two May 2019 tests" out; `fed_repo` kept everything before
  2019-09-17 at zero. None of the six reaches $1bn, so the material-use event is not affected.
- **Answer 5, the facility marker: not carried.** `fed_repo_facility` (none, temporary operations, standing facility)
  has no counterpart.
- **Answer 14, term repos outstanding: not carried.** The parent sums each operation's accepted amount on its operation
  date, overnight and term alike (`repo_accepted`), and emits no settlement or maturity date, so the amount outstanding
  cannot be derived from its fields. Take-up differs from `fed_repo_take_up` on 192 of the 466 dates from 2019-09-17
  to 2021-07-28 (for example 2019-09-25: 105.0 outstanding against 75.0 accepted that day).
- **Answer 14, the material-use event: the parent's amounts give the same events, but it has no event column.**
  `repo_accepted` counts each operation on its operation date, overnight and term alike, as answer 14 asks, and
  `fed_repo_accepted >= 1.0` gives `fed_repo_material_use` on every date through 2025-12-31: 190 events from 2019-09-17
  to 2021-07-28, 31 from 2021-07-29 to 2025-12-31, none before.
- **Days with no operation inside 2019-09-17 to 2021-07-28.** `fed_repo` left them missing (2020-04-09, 2020-07-02,
  2021-04-01); the parent reads them as zero.
- **Coverage.** The parent's snapshots end on 2025-12-31, and `fed_liquidity.assemble` reads any later row up to its
  `end` as zero take-up. The panel's standing-facility take-up from the parent's `nyfed_srf` ran to 2026-09-03; on
  2026-01-02, 2026-02-17, 2026-03-02 and 2026-04-15 it shows take-up of $9bn to $31bn that the parent's module, run
  past its snapshots, reads as zero. A caller must stop `end` at the snapshots' last date.
- **Smaller differences, not investigated:** two dates in 2021 to 2025 where the parent's amount and `nyfed_srf`'s
  differ by less than $0.1bn (2023-03-08: 0.0 against 0.056; 2024-09-24: 0.002 against 0.059).
- **Availability.** The parent reads a date at the later of 16:00 New York on the next business day and the Desk's
  recorded write time; `fed_repo` read it at 16:00 on the next weekday. The parent's reading is never earlier.
