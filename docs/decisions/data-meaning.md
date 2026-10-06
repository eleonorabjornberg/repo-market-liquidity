# Decision: data meaning for Phase 3, questions 1 to 13

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

## Checked against our sources (6 October 2026)

- **Question 1, the reinvestment regime: confirmed.** The FOMC implementation note of 29 October 2025 says: "Beginning on
  December 1, reinvest all principal payments from the Federal Reserve's holdings of agency securities into Treasury
  bills". The note of 10 December 2025 repeats it. Both are tracked under `tests/fixtures/snapshots/fomc_notes/pages/`.
  So since 1 December 2025, MBS paydowns are a composition shift from MBS into bills, neutral for reserves.
- **Question 1, the source:** H.4.1 table 1 carries a "Mortgage-backed securities" row in the same layout as the Treasury
  row, so the same archived releases give the realized MBS change.
- **Question 5, the 2019 to 2021 repo operations:** not yet checked against the NY Fed's operation history.

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
