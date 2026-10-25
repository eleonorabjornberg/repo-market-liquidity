# Research-log corrections

A merged pull request's body is not edited. When its research-log entry was wrong at the format in force on `main`, the
corrected entry is added here, under a heading `## Corrects the entry of #N (<link to the finding>)`, with exactly one
fenced `research-log` block. The push-path check (`scripts/check_log_entry.py --push-event`, `tests.yml`) reads the
correction in place of the merged body. The model repository copies the block here, not the body, into its
`docs/research/log.md`. `scripts/check_log_entry.py` parses this file; do not change its headings.

## Corrects the entry of #76 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/96)

Corrects #76's merged entry (finding #96, directive #100). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84; no figure or sentence is changed.

```research-log
### 2026-10-14 [H7] groundwork G6 · eleonorabjornberg/repo-market-liquidity#76
- Directive: eleonorabjornberg/repo-market-liquidity#74
- Step: H7m groundwork G6 (goalpost module and power study)
- Tier: development
- Pins: model 53e61af9b4175e854c196908d3c76b228c039667, panel digest acb77874e0ca2c9eeee1c33a229f5e12745e65bb1224088d52c391dbf54be2ab, snapshot none
- Tried: R plus a planted signal on 9 target gains, replayed over 60-, 125- and 250-day windows; variant count 0 (no candidate)
- Result: MME 0.05 detectable in 10 of 13 250-day windows that reach 10 events (power 15% over all 67 windows; 41% to 2020, 6% 2021-24); events are the constraint (221 in 1,570 days)
- Against kill: not applicable (no candidate scored); docs/decisions/measurement-protocol.md §5 and §9 unchanged
- Next: Eleonora sets the MME and the event floor (Q2); step 2 (candidate C) continues in plan order
```

## Corrects the entry of #114 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #114's merged entry (finding #175, directive #176). The only change is one phrase in the Result line: "withheld
by the lockbox after amendments" becomes "left out of the extract by the as-of rule, because their amendments were
filed after the development end", which says what happened (PR #128 later restored those rows) and avoids the word the
model's plain-language page test forbids. No figure is changed. Drafted for Eleonora (Eleonora's ruling of 24 October
2026 on #176, option (a)).

```research-log
### 2026-10-15 [H7] groundwork G5 · eleonorabjornberg/repo-market-liquidity#114
- Directive: #69 (her ruling on Q2, amended 15 October 2026)
- Step: groundwork G5 for H7m candidate D: State Street read at the bank of the G-SIB (IDRSSD 35301), in the main measure
- Tier: development
- Pins: parent 8fd2cf8; panel digest unchanged (4ddc3882…); slr_headroom 09c138ad… to 013b647e…
- Tried: matched each IDRSSD in the extract against the POR names and sizes; replaced 93619 (a trust subsidiary) with 35301; re-cut from the CDR files of 15 October 2026
- Result: inputs revised, nothing scored; State Street's ratio is 6.5–8.5% across 34 quarters; 9 Citibank and Goldman Sachs bank-quarters left out of the extract by the as-of rule, because their amendments were filed after the development end
- Against kill: not applicable; nothing scored
- Next: her ruling on whether the smaller G-SIB depository subsidiaries belong in the main measure (data-meaning row 16(c))
```

## Corrects the entry of #134 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #134's merged entry (finding #175, directive #176). The only change is the heading: `groundwork (input) ·
…#132` becomes `groundwork G8 · …#134`, the groundwork item #132 served (plan G8, as #141's entry reads `H7-G8`) and
the pull request that carried the entry. No figure or sentence is changed.

```research-log
### 2026-10-19 [H7] groundwork G8 · eleonorabjornberg/repo-market-liquidity#134
- Directive: #132
- Step: groundwork (input), the NY Fed reserve demand elasticity as a reported, never-deciding external check on H7m goalposts 1 and 3 (Lens B, repo-market-model#958)
- Tier: development
- Pins: parent 8fd2cf8c72e7d5c6e81c509651b684b690054a6f; panel 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999; workbook 59b9f49d21ac09ef385de933813775ee302f4b4c232d103e5699c1377ffeed43; snapshot rde 6edafdc786e9b99d8e43f540a52083ed843a086a43209d3df3bfd207023d9e80
- Tried: stored the NY Fed's latest RDE release, built a table of 80 estimates from the launch headline (2024-10-02) to the development end, read as public at the first third-Thursday 10:00 release at least 10 days after the estimate date, declared it under D1 and published it by digest
- Result: the 95% interval excludes zero on no date in the table; the main estimate changes sign on 4 dates, all inside noise around zero; nothing is scored and nothing is wired into a goalpost
- Against kill: not applicable, an input; the page serves one vintage, so first prints are not recoverable
- Next: a later H7m step reports the RDE beside goalposts 1 and 3 as "external check, not deciding"; the heading's G number waits on Eleonora
```

## Corrects the entry of #174 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #174's merged entry (finding #175, directive #176). The only change is the Result line: "reported, decides
nothing" becomes "reported only; it settles no question", the same meaning without the phrase the model's plain-language
page test forbids. No figure is changed. Drafted for Eleonora (her ruling of 24 October 2026, that the liquidity side
rewords).

```research-log
### 2026-10-23 [H7] step 4 · eleonorabjornberg/repo-market-liquidity#174
- Directive: eleonorabjornberg/repo-market-liquidity#144, H7m step 4: the account of the bank distribution for A and C (protocol section 8).
- Step: step 4
- Tier: development
- Pins: parent 08ff67e27bc3d7e357491cf8e1da59793702b3fb; panel digest 6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4 (version 4); stage docs/stages/h7-step4.md
- Tried: aggregate deployable liquidity under the three declared alternatives, per served day with 90% intervals, for C and CV1 to CV4 (shares and draws re-run and equal to the record) and for A's B and V1 to V6 (as defined and through the group machinery); D not reported (#142)
- Result: reported only; it settles no question
- Against kill: not applicable (protocol section 8: required, never decisive)
- Next: step 5 (goalposts under the protocol), after her reading of the marked questions
```

## Corrects the entry of #61 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #61's merged entry (finding #175, directive #176). Two changes, no figure: the Step line's "one lockbox read
from the parent" becomes "one read of the locked days from the parent" and "without the blind-tier row" becomes
"without the row for the locked final period", the same meaning without words the model's plain-language page test
forbids or would forbid; and the field name `Against the goalpost or kill` becomes `Against kill`, the name the shared
format has used since PR #84 (as for #76), which this repository's check requires. Drafted for Eleonora (her ruling of
24 October 2026, that the liquidity side rewords).

```research-log
### 2026-10-14 [H10] step 1 · eleonorabjornberg/repo-market-liquidity#61
- Directive: #59 (finding #55)
- Step: H10 step 1 and L1 inputs: one read of the locked days from the parent; the attribution entry checks the window is public; the FOMC snapshots re-cut without the row for the locked final period
- Tier: development
- Pins: parent 09640f5; panel digest unchanged; on_rrp_rate and srf_rate snapshots re-cut (digests in the PR)
- Tried: synthetic and tracked-panel leakage tests (tests/test_attribution.py, test_h8.py, test_snapshots.py), each with one recorded mutation
- Result: guards added, snapshots re-cut, nothing scored
- Against kill: not applicable; nothing scored
- Next: H10 step 2, after #48 merges and Eleonora decides finding #52
```
