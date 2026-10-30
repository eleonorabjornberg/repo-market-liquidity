# H10: second re-registration, prepared at the post-#1312 parent pin

**Prepared, not made.** This page is the record for Eleonora's re-registration of H10's frozen method at the parent's post-#1312 pin
(directive #200; her rulings of 29 October 2026: option (ii) on the pin, and (a) on H10's decision instant). It registers nothing and
is **hers to merge** (`needs-eleonora`). **Until she posts the registration on #23 herself, H10's registration of 22 October 2026
(commit `7838483`, digest `43bf1303…15bb`, parent `08ff67e`) stands, and nothing reads H10 at the new pin.** A changed method is a new
declaration with a new date (plan, H10, "Registration"); this is that declaration, for her to make. The precedent is
`docs/research/h10-reregistration.md` (#159), which is the record of the registration of 22 October and is not edited.

Development evidence only. It scores nothing and is not a verdict.

## Her answer to the sub-question, and where 16:00 stood

Her ruling (a), 29 October 2026, about 10:15 pm ET: **H10's own decision instant moves to 18:00 with the parent.** It is one line,
`src/repo_liquidity/h10_apply.py`:

```
DECISION_TIME = time(18, 0)
```

Every reading of the instant in H10's method follows it. Where 16:00 sat, and what became of it:

| Place | Was | Now |
|---|---|---|
| `h10_apply.py`, the `DECISION_TIME` line | `time(16, 0)` | `time(18, 0)` (the one line) |
| `h10_apply.py`, comment on `REPORT_DAYS` | "decision instant, 16:00" | "18:00" |
| `h10_apply.py`, `real_rule` docstring | "at the 16:00 decision instant" | "at the decision instant (`DECISION_TIME`)" |
| `h10_apply.py`, `real_rule` (`decision_time=DECISION_TIME`) and the record's `settings.decision_time` | follow the constant | follow the constant, unchanged text |
| `h10_live.py`, module docstring | "(16:00)" | "(`h10_apply.DECISION_TIME`, 18:00)" |
| `h10_live.py`, `decided_constants()["decision_time"]` | follows the constant | follows the constant (`18:00:00`), so the digest's `constants` part moves |
| `docs/research/h10-live-interface.md`, the Inputs row | "16:00 decision instant" | "decision instant, 18:00 (`h10_apply.DECISION_TIME`, one line)" |

Left unchanged, because each is a frozen or closed record of its own instant (the directive's step 3):
`src/repo_liquidity/curve_feature.py` (`DECISION_TIME = time(16, 0)`, Stage 4, frozen), `docs/decisions/measurement-protocol.md` (line 24, H7m,
closed) and `scripts/g6_power_study.py` (line 98, H7m, closed). Other modules that state `time(16, 0)` for their own stage
(`demand_curve`, `h7_estimator`, `h7_clean`, `h7_kink`, `live`) are Stage 2 to 5a and H7m code and are not H10's method; they are unchanged and not claimed here.
The H10 development records (`results/h10/`) were made at 16:00 and stand as records of that instant.

## The pin

| | At the registration (22 October) | At the new pin |
|---|---|---|
| Parent commit | `08ff67e27bc3d7e357491cf8e1da59793702b3fb` | `2032de4a7d7802289bc5a78dfc02599752bc7c5c` (repo-market-model#1315's merge commit; the model's `main` has since moved on, and moving to a later commit is a separate decision) |
| Parent published panel sha256 (its `metadata/funding_panel_manifest.json`) | `4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999` | `4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999` |
| Parent decision instant (that manifest's `decision_time`) | `16:00:00` | `18:00:00` |
| Phase 3 panel version H10 reads | 4, sha256 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4` | 5, sha256 `63fe5f7fd5ccae40e30aad729fab8f8f417a1323b717635a95aae727fb8143c1` |

The parent's published panel digest is the same at both pins, confirmed here against the parent at `2032de4`: the parent's panel
rebuilds to it from its tracked fixtures (`tests/test_parent_pin.py`). This repository's Phase 3 panel digest does move, so it is a new
panel version, version 5, as #149 named version 4 (`docs/stages/panel-v5.md`, `results/panel/v5_changes.json`). It differs from version 4 in 32
`srf_take_up` cells and nothing else, because of the parent's afternoon test-trade rule (#938), not because of the instant. Version 4 stays as
published.

## The digest, side by side

`h10_live.method_digest()` is one sha256 over the parts below, in this order, each as `name NUL length NUL bytes`
(`docs/research/h10-live-interface.md`, "The method digest"). The registered value reproduces from this repository at `7838483` with
the parent at `08ff67e` (both checked out clean for this page); the new one is computed from the tree this page is in, with the parent at `2032de4`.

| | |
|---|---|
| method_digest() as registered on #23, 22 October 2026 | `43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb` |
| method_digest() at the new pin | `54b5f151c757b1cff5d3ebe6e8ce202bd41cafc4d8104effb00f3da4617c8770` |
| record_sha256() | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` |

`record_sha256()` is the sha256 of `docs/decisions/h10-method.md` alone, the same as registered.

### The parts, as registered and at the new pin

| Part (a parent part is named by the pin in the digest; the pin is left out here) | sha256 as registered | sha256 at the new pin | Changed |
|---|---|---|---|
| `docs/decisions/h10-method.md` | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` | no |
| `src/repo_liquidity/attribution.py` | `2448043e6abe73699e72f0faa59bd07400877990df6b1079596c879aaa8ec9fb` | `9d58f1a2af787b6de12cabbf1a4a493504d8912f6ee0ae2444d9a58dce62ff74` | **yes** |
| `src/repo_liquidity/h10_apply.py` | `3719ff46de4cda28befc60464ed4664f3216a3d860728c60fde02bca9977239d` | `f7226b8f34fd41ba85fb1f78de82b554345082bc068adde0ed2caf2bc2bd0525` | **yes** |
| `src/repo_liquidity/h10_live.py` | `d6ae4c501f9ce36bb523bdf79e25cfa70cb08f9c79eaec6b8a7928cf5b2eca96` | `09433f895a1273cea0fb4c352539342aed2173f8f18340756fa618af90b5d953` | **yes** |
| `src/repo_model/onset.py` | `f45b6b249d5e39534de6bcef328ff568d1daf59a51fd9d48597e94b61c2df9e1` | `36e041343d52b54c599f35d0b4b2f9fc8abb088bdf61ba4872af831de8e6fb44` | **yes** |
| `src/repo_model/pressure.py` | `bb642c898c43ebdc43d551444114c549c2cce801c98a44513ddafea5af43cd08` | `bb642c898c43ebdc43d551444114c549c2cce801c98a44513ddafea5af43cd08` | no |
| `src/repo_model/asof.py` | `0c6dcd49364722ab7b28e4ba20e6c53b86dee2b3aa36d01b4234a6b7c33ba25c` | `07ae83df23a437816d585e602ce76e109187a2256c55ea45cd1eab9b101466ef` | **yes** |
| `src/repo_model/contract.py` | `56630a9f2dac6d143beba4ce203976c6870dec49fc0951d70aba20e87309038d` | `56630a9f2dac6d143beba4ce203976c6870dec49fc0951d70aba20e87309038d` | no |
| `src/repo_model/metrics.py` | `5d82815bc9095ce777f65b49012797c38cb4c5eea3fa3ceb6b61edeb2f0ddd17` | `5d82815bc9095ce777f65b49012797c38cb4c5eea3fa3ceb6b61edeb2f0ddd17` | no |
| `constants` | `dc42b52cd1ca94578b1d345ded1ca5f7f86b5b14435ed563b19a8457a30b9add` | `01fb8ea6deeb5b39b981aa42e392374dddaa7b42fb5c86606af6d90700b5da7d` | **yes** |

Why the digest moves: the parent parts are named by the pin, so it changes with the pin even for identical bytes; and six parts changed in
content: three files of this repository, two parent files and the constants.

## The five parent files H10 names

Compared byte for byte between clean checkouts of `08ff67e` and `2032de4`:

| File | Identical between the two pins |
|---|---|
| `src/repo_model/onset.py` | **no**: 8 lines added, a `LOCKBOX_CRPS` literal (#1058) that the lockbox test reads from the file's syntax tree. No code of the onset rule changed. |
| `src/repo_model/pressure.py` | yes |
| `src/repo_model/asof.py` | **no**: see below |
| `src/repo_model/contract.py` | yes |
| `src/repo_model/metrics.py` | yes |

**`asof.py` is a change in `InformationRule`, not a comment** (commit `dd4495c7`, repo-market-model#1060, "as-of rule: a group's observation instant is the
latest over its fields"; the same range also carries `39c42af5`, #1132, comment wording). The weekly-observation helper used to return
at the first non-weekly field of a group; it now computes each field's instant and takes the latest, so a group's instant no longer depends on the order of its fields.
The diff (13 lines added, 9 removed) is in `git diff 08ff67e 2032de4 -- src/repo_model/asof.py` of repo-market-model. Whether it
moves any read H10 makes is what the re-run below shows. **Ruled (Eleonora, 30 October 2026, Q1 (a)):** register at `2032de4` as it stands, and name the #1060
`InformationRule` change in the registration (a group's observation instant is the latest over its fields). The registration of 22 October named
`asof.py` at `08ff67e`; the one at `2032de4` names the changed file. See "Questions" below.

## The H10 files of this repository that changed

Against `7838483` (the registered commit): `h10_apply.py` (the instant, the panel version 4 to 5, comments), `h10_live.py` (a comment, the import, the
`registered_digest` guard of step 5 below, and the live read's guards, next section) and `attribution.py` (`episode_onsets` and `cross_check_onsets` take a
`check` for the dates they read, defaulting to the unchanged `check_development`). The method record is unchanged. A new file,
`src/repo_liquidity/h10_registration.py`, holds the registered digest and is **not** covered by the digest, because a registered digest in a covered
file could never equal itself. `git diff 7838483 HEAD -- src/repo_liquidity/attribution.py src/repo_liquidity/h10_apply.py src/repo_liquidity/h10_live.py` shows all of it.

## The live read and the lockbox (her ruling on repo-market-model#1324, option 2)

At `7838483` the live path called `attribution.check_development` on the days it read, so it refused every day of the blind tier (from 2026-09-04): no live
row could be produced. Her ruling of 30 October 2026 (relayed by the orchestrating session; model ledger items 84-85): the method reads only the days before
the report instant, and a locked tier that no comparison scores does not refuse it. **No change to the parent's lockbox.** In this version:

* **No day after the report instant is read.** `h10_live.check_no_row_after_report` raises `LookAheadError` for any row dated after `report_date`, before any fit,
  placebo or null is built. It is a guard that refuses, not a trim. (Rows between the last public day and the report day, which the report's own instant cannot
  have seen in full, are handed in and not read; the window actually read is checked with `check_window_public`, as before.)
* **A tier some comparison scores stays refused**, through `lockbox.require_unlocked` (`h10_live.check_scored_tiers`). The open-ended `blind` tier is the one the live path
  reads (`h10_live.LIVE_READABLE_TIERS`). In the declaration at the pin (`metadata/lockbox.json`, identical at `2032de4` and at the model's `main`), the `near_blind` tier
  (2026-01-01 to 2026-09-03) is **opened** (2026-10-05, #151), so it is ordinary history that comparisons may score and nothing refuses it; the `blind` tier is locked and
  **no comparison scores it**: scoring protocol #640, rulings of 13 October 2026, item 3, says scoring confirmation days *opens* the blind tier days, each opening her own
  attested action, and the lockbox record keeps the blind tier from every comparison until then. So no locked tier that a comparison scores exists today. If the near-blind tier
  were locked again, or a tier added, the live path would refuse its days.
* **The development path is unchanged.** `h10_apply.load_development` keeps `check_development` (development ends on 2025-12-31).

## Do H10's development tables move at 18:00 on version 5?

`scripts/h10_v5_check.py` (the check of #152, one pin later) re-runs, on panel version 5 with the parent at `2032de4` and the instant at 18:00, the step 2
application (`results/h10/development.json`), its ON RRP interaction sensitivity (`results/h10/sensitivity_onrrp_interaction.json`), its regime
sensitivity (`results/h10/sensitivity_onrrp_regimes.json`) and the placebo-floor comparison (`results/h10/placebo_floor_2bp.json`), at the published
records' seeds and episodes, and compares each, key by key, with the tracked record. The records name panel version 1 or 4, the pin they were made at and
`settings.decision_time` 16:00:00; those three paths may differ and are printed.

Result (run on 30 October 2026, the parent at `2032de4`, panel version 5, two workers, the published draws and seeds):

```
panel version 5, sha256 63fe5f7fd5ccae40e30aad729fab8f8f417a1323b717635a95aae727fb8143c1, 2104 rows to 2026-09-03, decision instant 18:00:00
development: development.json: exempt paths that differ: ['/panel/sha256', '/panel/version', '/parent_commit', '/settings/decision_time']; identical elsewhere
interaction: sensitivity_onrrp_interaction.json: exempt paths that differ: ['/panel/sha256', '/panel/version', '/parent_commit', '/settings/decision_time']; identical elsewhere
regimes: sensitivity_onrrp_regimes.json: exempt paths that differ: ['/panel/sha256', '/panel/version', '/parent_commit', '/settings/decision_time']; identical elsewhere
placebo floor: placebo_floor_2bp.json: exempt paths that differ: ['/parent_commit']; identical elsewhere
```

All four rebuilt records are identical to the tracked records at every key except the three exempt paths: `panel` (`version`, `sha256`: the records
name version 1 or 4), `parent_commit` (each record names the pin it was made at) and `settings.decision_time` (16:00:00 in the records, 18:00:00 in the rebuilt
rows). The placebo-floor record carries no instant, so only `parent_commit` differs there. That covers every episode's shares, intervals, placebo
and benchmark readings, the selection null, the counts and the outcome. **H10's development, interaction, regimes and placebo-floor tables are
unchanged at 18:00 on version 5 with the parent at `2032de4`, including the changed `asof.py` and `onset.py`.** The published records are not edited; they stay as published and
name the pin and the instant they were made at.

## Live runs in the gap (step 5)

Between the merge of the pull request that adds this page and the new pin, and her new registration on #23, `main` carries the new pin and the new method,
but the registration in force is the one of 22 October. **A live H10 run in that window uses the registered code:** this repository at commit `7838483` with the parent at
`08ff67e`, which together give digest `43bf1303…15bb`. It does not use `main`.

This is enforced, not only stated: `h10_live.attribute_onset` calls `h10_registration.check_registered(method_digest(), registered_digest)` before it reads
anything, and raises `ValueError` when this code's digest is not `h10_registration.REGISTERED_DIGEST` (`43bf1303…15bb` today). On `main` it therefore refuses until
her registration updates that constant in the pull request that follows it (`src/repo_liquidity/h10_registration.py`; no other change does). The live
job passes nothing for `registered_digest`. `tests/test_h10_registration.py` tests the refusal, with a recorded mutation. **The 22 October method refuses every live day:** `7838483` calls `check_development` on the days it reads, and every live day is in the blind tier, so no live row can be produced in the gap, by that code or by a mistake. A job that calls this repository at a commit it pins can keep calling `7838483` (panel version 4, the parent at `08ff67e`), or pause; it cannot produce an H10 row from `main` by accident.

## Questions for Eleonora (all three ruled on 30 October 2026)

1. **Ruled: (a).** (Eleonora, 30 October 2026, repo-market-model#1324 ruling relayed by the orchestrating session: register at `2032de4` and name the #1060 `InformationRule` change.) **Is the registration to name `asof.py` as changed at `2032de4`?** `InformationRule`'s group instant changed (#1060). The re-run above shows the effect on H10's tables
   (all four tables are identical, as printed above). Options: (a) register at `2032de4` as it stands, naming the change [recommended, if the tables are unmoved]; (b) ask the model
   repo to confirm, in its own words, that #1060 does not change an H10 read, before registering. Default if unanswered by the next 5 pm batch: (a) is only a draft; nothing is registered.
2. **Ruled: her default, no change (30 October 2026).** **ON RRP availability (`docs/decisions/data-meaning.md`, lines 100-101).** The page reads repo-operation results "at the later of 16:00 New York on the next business day and
   the Desk's recorded write time". The parent did not move that reading: `repo_model.fed_liquidity.DECISION_TIME` stays 16:00 on purpose (`LEGACY_DECISION_TIME`), with the comment that
   whether to re-read the same-day take-up at the new decision instant is "a data-meaning question that is not settled here" (#1312). This repository's data-meaning page is unchanged.
   **Flag, not settled:** whether the Desk's recorded write time should now be compared with 18:00 rather than 16:00 is hers.
3. **Ruled: her default, no change (30 October 2026; the stale `scarcity.py` cites stay in `MOVED_AT_PIN`).** **Panel version for later work.** Stage 4's freeze and the closed H7 records name versions 3 and 4 and stay as published; any later study reads version 5.

## The registration text

For Eleonora to post herself on #23. Nothing here is posted by the relay.

````
Registration (H10), at the post-#1312 parent pin and the 18:00 decision instant. I register H10's frozen attribution method again:
- repo-market-liquidity commit <the merge of the pull request that adds docs/research/h10-reregistration-2.md>;
- method digest `54b5f151c757b1cff5d3ebe6e8ce202bd41cafc4d8104effb00f3da4617c8770` (`h10_live.method_digest()`, over docs/decisions/h10-method.md, attribution.py, h10_apply.py, h10_live.py, the parent files onset.py, pressure.py, asof.py, contract.py and metrics.py at the pinned parent commit, and the decided constants including ON_RRP_DEPLETION_BREAK_BN and the decision instant);
- method record docs/decisions/h10-method.md, sha256 `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` (unchanged since the registration of 19 October);
- the decision instant is 18:00 New York time (`DECISION_TIME = time(18, 0)` in src/repo_liquidity/h10_apply.py), moved from 16:00 with the parent (my ruling of 29 October 2026, (a) on #200);
- parent repo-market-model at 2032de4a7d7802289bc5a78dfc02599752bc7c5c, panel sha256 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999 (the parent's published panel); the Phase 3 panel H10 reads is version 5, sha256 `63fe5f7fd5ccae40e30aad729fab8f8f417a1323b717635a95aae727fb8143c1`;
- the parent file asof.py changed between 08ff67e and 2032de4: InformationRule's group observation instant is the latest over its fields (repo-market-model#1060); I register at 2032de4 with that change (my ruling of 30 October 2026, Q1 (a)); H10's four development tables are unchanged by it;
- the live read: no row dated after the report day is read (a row after it is refused), the open-ended blind tier of the parent's lockbox is read, and a locked tier that a comparison scores stays refused (my ruling of 30 October 2026 on repo-market-model#1324, option 2; no change to the parent's lockbox);
- the full account is docs/research/h10-reregistration-2.md.

This replaces my registration of 22 October 2026 (commit 7838483, digest 43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb, parent 08ff67e27bc3d7e357491cf8e1da59793702b3fb, decision instant 16:00) from the date of this comment. From now on the method does not change; a changed method is a new declaration with a new date. Each new onset is attributed with `h10_live.attribute_onset` and reported within 10 business days, labelled prospective, against the outcome rule in plan.md. Each live row carries both the floored and the unfloored placebo reading and a stamp of the rows and the parent code it used. A follow-up pull request sets `h10_registration.REGISTERED_DIGEST` to the digest above.
````

The commit to name is the merge commit of the pull request that adds this page, so she fills it in once she has merged; the digest above holds for that commit and for
this branch's head alike, because `h10_registration.py` is not covered and nothing after the page changes a covered file. The sha256 of this page itself is in the
pull request body (a page cannot state its own hash).
