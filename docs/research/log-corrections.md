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
