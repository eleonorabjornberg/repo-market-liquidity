# Stage 1b, first wave: plan

**Written 6 October 2026, before anything is built.** Eleonora agreed it on 6 October 2026. Its scope is Nicholas
Beroud's answer 7 (`docs/decisions/data-meaning.md`): start narrow, with pricing and the Fed's facilities, which are
daily and mostly declared already. It is built after the Stage 1a correction
(`docs/stages/stage-1a-correction.md`).

## The indicators

What the parent already declares is switched on in Phase 3's overlay, as Stage 1a did for ON RRP and H.8. Nothing new
is fetched unless the table says so.

| Indicator | Definition | Source |
|---|---|---|
| SOFR − IORB | bp | In the panel (`sofr`, `iorb`) |
| TGCR and BGCR against SOFR | TGCR − SOFR, BGCR − SOFR, bp | In the panel (`tgcr`, `bgcr`) |
| Percentile dispersion | SOFR p75 − p25 (in the panel); p99 − p1 and p1 − BGCR (the specials proxy of answer 8) | p25 and p75 in the panel; p1 and p99 from the parent's `nyfed_sofr` declaration (fields `SOFR_p1`, `SOFR_p99`), switched on |
| SOFR − EFFR | bp | The parent's `nyfed_effr` declaration, switched on |
| TGCR − ON RRP rate | bp; Nicholas's reading of ON RRP (answer 12) | `tgcr` and the ON RRP rate already in force (Stage 1a's scheduled input) |
| ON RRP buffer present or gone | the parent's flag (#232), from take-up | `on_rrp` (Stage 1a) and the parent's rule |
| Standing facility | distance from SOFR to the facility's rate (the continuous input, answers 2 and 13) and the material-use event | Stage 1a and its correction |
| SOMA flows | weekly Treasury and MBS changes, caps | Stage 1a and its correction |
| TGA | level and daily change | In the panel (`tga`) |

Each switched-on field keeps the parent's availability declaration. Each new derived column is computed only from
columns already admitted at the same decision instant.

## What it must show

1. Every input passes the parent's guards. Each newly switched-on source has a leakage test with one recorded mutation
   that kills it.
2. The parent's published panel still rebuilds to its digest, and the earlier stages' records regenerate unchanged.
3. Coverage from 2018-04-03 per column, with every hole and refusal listed.
4. The measurement break is declared: mandatory clearing of Treasury repo (2027-06-30) changes what SOFR volume and
   dispersion measure (answer 11), so any column built on them carries that break into the live filter.
5. No scores and no figures.

## Later waves (not planned here)

- **Second:** dealer intermediation and cash supply and demand: FR 2004 positions and fails, and the CFTC TFF
  leveraged-fund positions (released Friday for Tuesday; that lag is declared). Collateral scarcity (SOMA securities
  lending, fails, DVP − BGCR) stays on its own axis, apart from cash scarcity (answer 8).
- **Last:** segment distribution, because of vintage issues.
- **Separately:** the H.8 bank-size split (cash assets of large domestic, small domestic and foreign-related
  institutions, answer 6), for Stage 4's sensitivity run. Haircuts have no point-in-time source (answer 10).
