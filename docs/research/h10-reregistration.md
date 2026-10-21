# H10: re-registration prepared at the new parent pin

**Prepared, not made.** This page is the record for Eleonora's re-registration of H10's frozen method at the new parent pin
(her ruling of 20 October 2026 on #149, option 2; directive #152). It registers nothing and changes no code the digest
covers beyond what #155 already merged. **Until she merges the pull request that adds this page and posts the registration
on #23 herself, H10's registration of 19 October 2026 (commit `4cd041e`, digest `cc7bab6e…49b1`, parent `8fd2cf8`)
stands, and nothing reads H10 at the new pin.** A changed method is a new declaration with a new date (plan, H10,
"Registration"); this is that declaration, for her to make.

Development evidence only. It scores nothing and is not a verdict.

## The pin

| | At the registration (19 October) | At the new pin |
|---|---|---|
| Parent commit | `8fd2cf8c72e7d5c6e81c509651b684b690054a6f` | `08ff67e27bc3d7e357491cf8e1da59793702b3fb` |
| Parent published panel sha256 (its `metadata/funding_panel_manifest.json`) | `4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999` | `4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999` |

The parent's published panel digest is the same at both pins. The Phase 3 panel that H10 reads is this repository's own
build, version 4 since #149 (sha256 `6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4`); version 1 (the
panel the published H10 records name) stays as published.

## The digest, side by side

`h10_live.method_digest()` is one sha256 over the parts below, in this order, each as `name NUL length NUL bytes`
(`docs/research/h10-live-interface.md`, "The method digest"). Both values were computed from a clean checkout of the parent
at the named pin, the old one from this repository at `4cd041e`, the new one from the tree this page is in.

| | |
|---|---|
| method_digest() at 8fd2cf8, registered on #23 | `cc7bab6ea31ef51c839b17b237a8b92bd12afa60c191fe91f15d33286a1249b1` |
| method_digest() at the new pin | `43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb` |
| record_sha256() | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` |

The old digest reproduces from `4cd041e` with the parent at `8fd2cf8`. `record_sha256()` is the sha256 of
`docs/decisions/h10-method.md` alone, the same at both.

### The parts, each at both pins

| Part (a parent part is named by the pin in the digest; the pin is left out here) | sha256 at 8fd2cf8 | sha256 at the new pin | Changed |
|---|---|---|---|
| `docs/decisions/h10-method.md` | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` | `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` | no |
| `src/repo_liquidity/attribution.py` | `2448043e6abe73699e72f0faa59bd07400877990df6b1079596c879aaa8ec9fb` | `2448043e6abe73699e72f0faa59bd07400877990df6b1079596c879aaa8ec9fb` | no |
| `src/repo_liquidity/h10_apply.py` | `711e69a3773da2336d5c1c9b5d5182febb7e5defad8744cc54315f09f6e371a0` | `3719ff46de4cda28befc60464ed4664f3216a3d860728c60fde02bca9977239d` | **yes** |
| `src/repo_liquidity/h10_live.py` | `d6ae4c501f9ce36bb523bdf79e25cfa70cb08f9c79eaec6b8a7928cf5b2eca96` | `d6ae4c501f9ce36bb523bdf79e25cfa70cb08f9c79eaec6b8a7928cf5b2eca96` | no |
| `src/repo_model/onset.py` | `f45b6b249d5e39534de6bcef328ff568d1daf59a51fd9d48597e94b61c2df9e1` | `f45b6b249d5e39534de6bcef328ff568d1daf59a51fd9d48597e94b61c2df9e1` | no |
| `src/repo_model/pressure.py` | `bb642c898c43ebdc43d551444114c549c2cce801c98a44513ddafea5af43cd08` | `bb642c898c43ebdc43d551444114c549c2cce801c98a44513ddafea5af43cd08` | no |
| `src/repo_model/asof.py` | `0c6dcd49364722ab7b28e4ba20e6c53b86dee2b3aa36d01b4234a6b7c33ba25c` | `0c6dcd49364722ab7b28e4ba20e6c53b86dee2b3aa36d01b4234a6b7c33ba25c` | no |
| `src/repo_model/contract.py` | `56630a9f2dac6d143beba4ce203976c6870dec49fc0951d70aba20e87309038d` | `56630a9f2dac6d143beba4ce203976c6870dec49fc0951d70aba20e87309038d` | no |
| `src/repo_model/metrics.py` | `5d82815bc9095ce777f65b49012797c38cb4c5eea3fa3ceb6b61edeb2f0ddd17` | `5d82815bc9095ce777f65b49012797c38cb4c5eea3fa3ceb6b61edeb2f0ddd17` | no |
| `constants` | `dc42b52cd1ca94578b1d345ded1ca5f7f86b5b14435ed563b19a8457a30b9add` | `dc42b52cd1ca94578b1d345ded1ca5f7f86b5b14435ed563b19a8457a30b9add` | no |

Why the digest moves: two things, and only two. The parent parts are named by the pin (`parent@<commit>:<path>`), so the
digest changes with the pin even though their bytes did not. And `h10_apply.py` changed.

## The five parent files H10 names

Each was compared byte for byte between a clean checkout of `8fd2cf8` and one of `08ff67e`, and with the git history of the
range (no commit between the two pins touches any of the five).

| File | Identical between 8fd2cf8 and the new pin |
|---|---|
| `src/repo_model/onset.py` | yes |
| `src/repo_model/pressure.py` | yes |
| `src/repo_model/asof.py` | yes |
| `src/repo_model/contract.py` | yes |
| `src/repo_model/metrics.py` | yes |

All five are identical, so there is no diff to show and nothing in the parent changes what H10's method does: the onset
rule and its cross-check, `InformationRule`, `ON_RRP_DEPLETION_BREAK_BN` and the stationary bootstrap are the ones that were
registered.

## The one covered file that changed: `h10_apply.py`

**This page does not meet the directive's "no file of this repository that the digest covers changed" as written, and says
so.** Directive #152 asks to confirm that no file of this repository that the digest covers changed, the pin only. One did,
before this page: `src/repo_liquidity/h10_apply.py`, in #155 (commit `3193f0b`, "H10 reads version 4"), under Eleonora's
ruling (Q1 on #149) that panel version 4 is the new panel. The orchestrating session's note on #152 (21 October 2026) names
this. This pull request changes no covered file. The other three covered files, the record and the constants are unchanged.

The diff of `h10_apply.py` against `4cd041e`:

```
-#: The panel the application reads: version 1, the published columns plus the built ON RRP take-up, to the development end.
-PANEL_VERSION = 1
+#: The panel the application reads: the published columns plus the built ON RRP take-up, to the development end. Version 4
+#: since the pin moved to 08ff67e (#149; ...): version 1 is a record that no longer rebuilds, and the
+#: published H10 records name it (`panel.version` in each), so a reader that checks one against its panel passes that version.
+PANEL_VERSION = 4
 ...
-def load_development():
+def load_development(version: int = PANEL_VERSION):
     (docstring: "Rebuilds `version` (the current one by default) ...")
-        manifest = panel.build(path, version=PANEL_VERSION)
-        recorded = panel.load_manifest(PANEL_VERSION)
+        manifest = panel.build(path, version=version)
+        recorded = panel.load_manifest(version)
-            raise ValueError(f"panel version {PANEL_VERSION} rebuilt to ...")
+            raise ValueError(f"panel version {version} rebuilt to ...")
```

What it changes in H10's method: the default panel version, from 1 to 4. The attribution (`attribution.py`), the drivers
(`treasury_settlement`, `tga`, `reserve_balances`, `quarter_end`, `on_rrp`), the window, the placebo, the bootstrap, the
null, the outcome rule and every constant are untouched. Version 4 differs from version 1 in `srf_take_up` alone
(`docs/stages/panel-v4.md`), which is not one of H10's drivers.

### Do H10's development tables move on version 4?

`scripts/h10_v4_check.py` re-runs, on panel version 4 and at the published records' pin, seeds and episodes: the step 2
application (`results/h10/development.json`), its ON RRP interaction sensitivity
(`results/h10/sensitivity_onrrp_interaction.json`), its regime sensitivity (`results/h10/sensitivity_onrrp_regimes.json`)
and the placebo-floor comparison (`results/h10/placebo_floor_2bp.json`), and compares each, key by key, with the tracked
record. Only `panel` (the records name version 1) is allowed to differ.

Result (run on 21 October 2026, the parent at `08ff67e`, four workers, the published draws and seeds): all four rebuilt
records are identical to the tracked records at every key except `parent_commit` (each tracked record names `8fd2cf8`, the
pin it was made at; the rebuilt one names the new pin); `panel` (version 4 against version 1) was exempt from the comparison. That covers every
episode's shares, intervals and placebo and benchmark readings, the selection null, the counts and the outcome. **H10's
development, interaction, regimes and placebo-floor tables are unchanged on version 4.** The published records are not
edited; they stay as published, and name version 1.

```
panel version 4, sha256 6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4, 2104 rows to 2026-09-03
development: development.json: DIFFERS at /parent_commit
interaction: sensitivity_onrrp_interaction.json: DIFFERS at /parent_commit
regimes: sensitivity_onrrp_regimes.json: DIFFERS at /parent_commit
placebo floor: placebo_floor_2bp.json: DIFFERS at /parent_commit
```

Those are the run's own lines, printed with its first filter, which exempted `/panel` only; the only path that differed is `/parent_commit`. The committed script also exempts
`/parent_commit`, so it prints "identical outside /panel and /parent_commit" for each; the run itself was not repeated
after that one-line change to the filter.

## The registration text

For Eleonora to post herself on #23. Nothing here is posted by the relay.

````
Registration (H10), at the new parent pin. I register H10's frozen attribution method again, under the new pin:
- repo-market-liquidity commit <the merge of the pull request that adds docs/research/h10-reregistration.md>;
- method digest `43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb` (`h10_live.method_digest()`, over docs/decisions/h10-method.md, attribution.py, h10_apply.py, h10_live.py, the parent files onset.py, pressure.py, asof.py, contract.py and metrics.py at the pinned parent commit, and the decided constants including ON_RRP_DEPLETION_BREAK_BN);
- method record docs/decisions/h10-method.md, sha256 `642fe092ca6d553fb5e12e263162869b096fa19e6cb7bb46c79c43cbc0fb67a9` (unchanged since the registration of 19 October);
- parent repo-market-model at 08ff67e27bc3d7e357491cf8e1da59793702b3fb, panel sha256 4ddc3882cd6d406b11e1088f8ff6195e16dde175a0ad6818abe40dd5bdac8999 (the parent's published panel); the Phase 3 panel H10 reads is version 4, sha256 6415651da6095e8d2942ab3ff344211b7fa32e7488eff622b04e18d72de822a4;
- the full account is docs/research/h10-reregistration.md.

This replaces my registration of 19 October 2026 (commit 4cd041eb3adb25aed290980ad2dfe2d4e7667ac2, digest cc7bab6ea31ef51c839b17b237a8b92bd12afa60c191fe91f15d33286a1249b1, parent 8fd2cf8c72e7d5c6e81c509651b684b690054a6f) from the date of this comment. From now on the method does not change; a changed method is a new declaration with a new date. Each new onset is attributed with `h10_live.attribute_onset` and reported within 10 business days, labelled prospective, against the outcome rule in plan.md. Each live row carries both the floored and the unfloored placebo reading and a stamp of the rows and the parent code it used.
````

The commit to name is the merge commit of the pull request that adds this page, so she fills it in once she has merged;
the digest above holds for that commit and for this branch's head alike, because the pull request changes no covered file.
The sha256 of this page itself is in the pull request body (a page cannot state its own hash).
