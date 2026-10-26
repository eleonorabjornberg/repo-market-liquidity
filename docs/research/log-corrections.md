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

## Corrects the entry of #32 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #32's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-12 [H7] groundwork G2 · eleonorabjornberg/repo-market-liquidity#32
- Directive: eleonorabjornberg/repo-market-liquidity#28
- Step: H7m groundwork G2 (measurement-protocol.md v1), with the plan and the research-log check for H7 and H10
- Tier: development
- Pins: model 490f23d4f29c85eb1778f647fa2111855a48bc2b, panel digest 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999, snapshot none
- Tried: committed the decided plan and protocol text from #20 and wrote the log check; variant count 0
- Result: plan and rules recorded, nothing scored
- Against kill: not applicable; M1 (docs/research/plan.md, H7m milestones) is met when this merges
- Next: H7 step 1 (#22) after repo-market-model#626; H10 step 1 (#23); inputs #25, then #26 and #27
```

## Corrects the entry of #33 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #33's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-13 [H10] step 1 · eleonorabjornberg/repo-market-liquidity#33
- Directive: eleonorabjornberg/repo-market-liquidity#23
- Step: H10 development 1 (method declared)
- Tier: development
- Pins: model 490f23d4f29c85eb1778f647fa2111855a48bc2b, panel digest 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999, snapshot none
- Tried: the method on synthetic episodes with planted shares; variant count 1
- Result: method declared, nothing applied
- Against kill: not applicable (descriptive; the outcome rule is fixed in docs/research/plan.md, H10, and is not applied)
- Next: Eleonora reviews and merges the record, then step 2 applies the frozen method to every development onset once
```

## Corrects the entry of #34 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #34's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-13 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#34
- Directive: #25 (L1), groundwork for H7m and H10
- Step: inputs declared and published as digest-named snapshots; not a hypothesis step
- Tier: development
- Pins: parent 490f23d4f29c85eb1778f647fa2111855a48bc2b; panel 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999
- Tried: parent validators on the three declarations; leakage and staleness guards with recorded mutations; tables checked against federalreserve.gov through 29 Jul 2026 and the 16 Sep 2026 note; snapshots built and rebuilt
- Result: inputs built, nothing scored
- Against kill: none applies; no estimate or score
- Next: L2 (#26), the H.8 bank groups, on the same snapshot convention once Eleonora has reviewed it
```

## Corrects the entry of #35 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #35's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-13 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#35
- Directive: eleonorabjornberg/repo-market-liquidity#22
- Step: H7m development 1 (estimand and estimator)
- Tier: development
- Pins: model 09640f5, panel digest 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999, snapshot none
- Tried: deployable liquidity as the parent's reserves ratio minus the fitted kink of the refit in force, with a bootstrap interval; variant count 1
- Result: built, nothing scored
- Against kill: not applicable (no goalpost is read before step 5, docs/decisions/measurement-protocol.md §3-§5)
- Next: step 2 (candidate C, bank groups) once #26 is merged; step 5 scores R, S, R+S and the estimate under protocol §5
```

## Corrects the entry of #38 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #38's merged entry (finding #175, directive #176). Two changes, no figure or sentence: the field name `Against
the goalpost or kill` becomes `Against kill`, as for #76, and the heading's `L6 red-main fix` becomes `groundwork G1`, the
format's form. The mapping to the plan's groundwork list is a proposal for Eleonora: G1 is the nearest item (the entry
is groundwork on a pin or an input read at it), and the plan has no item that names it exactly.

```research-log
### 2026-10-13 [H7] groundwork G1 · eleonorabjornberg/repo-market-liquidity#38
- Directive: eleonorabjornberg/repo-market-liquidity#36
- Step: groundwork (L6): snapshot manifests regenerated at parent pin 09640f5; guard for pin bumps
- Tier: development
- Pins: model 09640f5bb4063da150e09a285d242cd28db1c136, panel digest 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999, snapshot on_rrp_rate fa35581f…, srf_rate d4ded3b0…, runoff_caps ff413b06… (all unchanged)
- Tried: rebuilt the three manifests with scripts/build_snapshots.py; variant count 1
- Result: main green again; nothing scored
- Against kill: not applicable (no estimate made; docs/decisions/evaluation.md:3)
- Next: lift the hold on #24 once main's push CI is green
```

## Corrects the entry of #39 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #39's merged entry (finding #175, directive #176). Two changes, no figure or sentence: the field name `Against
the goalpost or kill` becomes `Against kill`, as for #76, and the heading's `L5 agency securities input` becomes `groundwork G1`, the
format's form. The mapping to the plan's groundwork list is a proposal for Eleonora: G1 is the nearest item (the entry
is groundwork on a pin or an input read at it), and the plan has no item that names it exactly.

```research-log
### 2026-10-13 [H7] groundwork G1 · eleonorabjornberg/repo-market-liquidity#39
- Directive: eleonorabjornberg/repo-market-liquidity#30
- Step: groundwork (L5): agency debt first prints as an input; "agency securities" = agency debt plus MBS (answer 15)
- Tier: development
- Pins: model 09640f5bb4063da150e09a285d242cd28db1c136, panel digest 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999, snapshot agency_securities 71921036…, h41_agency_first_print.csv 6c5a387a…
- Tried: fetched 454 weekly releases (2017-12-27 to 2026-09-02) and cross-checked each page's Treasury and MBS rows against the tracked extracts; variant count 1
- Result: input built, nothing scored
- Against kill: not applicable (no estimate made; docs/decisions/evaluation.md:3)
- Next: H7 step 2 waits on step 1's review (Step by step); L2 and L3 add their sources under declarations/
```

## Corrects the entry of #42 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #42's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-13 [H7] groundwork G4 · eleonorabjornberg/repo-market-liquidity#42
- Directive: #26 (L2, H.8 bank-group series as first prints, with answer 17)
- Step: groundwork G4 for H7m, before step 2 candidate C
- Tier: development
- Pins: parent repo-market-model 09640f5; panel 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999; snapshot h8_groups 1069af546ca0c5d3d69190b680dbc617557d3bbac0798f6a1e12d155f9f1f7f9
- Tried: read cash assets and total assets of large domestic, small domestic and foreign-related banks from all 456 archived H.8 releases, first prints only, and declared the input under the parent's validators
- Result: inputs built, nothing scored. 452 weeks, 2017-12-27 to 2026-08-19, no hole, no refusal; the groups' total assets sum to the parent's all-banks first print within 0.1 in every week; the lines are restated in 451 of 452 weeks and the large and small groups are reclassified against each other in 13 releases; 43 dated breaks from the notes archive
- Against kill: no goalpost is tested here; this is an input, not a measurement
- Next: the quarterly anchor and the weekly scaling (a directive for Eleonora to queue); H7 step 2 candidate C reads this series only after its answer-17 caveat is named in any derived reserves series
```

## Corrects the entry of #48 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #48's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-14 [H10] step 1 · eleonorabjornberg/repo-market-liquidity#48
- Directive: #45 (L-series), her ruling on #37
- Step: H10 step 1 completed: the method's six values recorded as decided; placebo count 5 to 20; fixed-coefficient shares reported
- Tier: development
- Pins: parent 09640f5; no panel digest change, no snapshot change
- Tried: synthetic episodes only (tests/test_attribution.py); no real episode attributed
- Result: nothing scored; full suite passes
- Against kill: not applicable; no episode attributed (outcome rule unchanged)
- Next: H10 step 2 (apply the method to the development onsets), queued only after this PR merges
```

## Corrects the entry of #51 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #51's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#51
- Directive: #47 (G4, H.8 group reclassifications as structural breaks)
- Step: H7 groundwork G4: the 13 large/small restatements and the 2023 failures read against the H.8 notes; breaks flagged in the h8_groups snapshot
- Tier: development
- Pins: parent 09640f5; h8_groups snapshot 326466ae847af5c5be0a462d0a71e6d4022fc792816a1c7f57ad1a9e8ee022fe
- Tried: the Notes on Data page (43 notes in range) and 26 archived release pages; nothing scored
- Result: breaks labelled from the notes, nothing scored: 0 labelled, 17 unexplained (13 restatements, 4 failures of 2023)
- Against kill: not applicable; nothing scored
- Next: H7 step 2 (candidate C, bank groups), after #43; a rule for a difference across a break is hers
```

## Corrects the entry of #60 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #60's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#60
- Directive: #58 (finding #53)
- Step: H7m step 1 fix: the as-of estimator runs the parent's rule.check and imports its date extension
- Tier: development
- Pins: parent 09640f5; no panel digest change, no snapshot change
- Tried: synthetic late and stale reads (tests/test_h7_estimator.py); the development estimate path before and after
- Result: guard added, nothing scored; estimate path byte-identical on the development panel
- Against kill: not applicable; nothing scored
- Next: H7 step 2 (#41), after #43, #47 and the parent's fix for finding #54
```

## Corrects the entry of #68 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/175)

Corrects #68's merged entry (finding #175, directive #176). The only change is the field name, `Against the goalpost or
kill` to `Against kill`, which is the name the shared format has used since PR #84 (as for #76); no figure or sentence is changed.

```research-log
### 2026-10-14 [H7] step 1 · eleonorabjornberg/repo-market-liquidity#68
- Directive: #65 (finding #54)
- Step: groundwork before H7 step 2 (#41): bump the parent pin to 53e61af (the fit_level tie fix), regenerate the snapshot manifests
- Tier: development
- Pins: parent 53e61af (was 09640f5); panel digest unchanged (4ddc3882…); no snapshot digest moved
- Tried: re-ran the H7 step 1 real-time path (81 refits, development days to 2025-12-31) at both pins and compared every refit and estimate
- Result: pin bumped; estimate path unchanged; one refit unfitted at both pins (2019-04-04, too few pairs); nothing scored
- Against kill: not applicable; nothing scored
- Next: H7 step 2 (#41), after #43
```

## Corrects the entry of #185 (https://github.com/eleonorabjornberg/repo-market-liquidity/issues/192)

Corrects #185's merged entry (finding #192, directive #192, from model PR #1250). The only change is the Result line: the
test count is removed, because the model's `COUNT_CLAIM` refuses a numeral counting tests in a published document and
blocks are copied verbatim. No other line and no figure is changed; nothing was scored.

```research-log
### 2026-10-26 [H7] groundwork G8 · eleonorabjornberg/repo-market-liquidity#185
- Directive: #184
- Step: groundwork, shared research log: the two #76 correction tests collected again, and a guard against a repeated test class name
- Tier: development
- Pins: parent 08ff67e27bc3d7e357491cf8e1da59793702b3fb; panel digest unchanged (4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999)
- Tried: renamed the second TrackedCorrectionsTests, moved every class above the main guard, checked #76 among the corrections, added tests/test_class_names.py
- Result: test_log_push collects the two #76 correction tests again and the full suite passes; nothing scored, no figure or record changed
- Against kill: not applicable; nothing scored
- Next: none
```
