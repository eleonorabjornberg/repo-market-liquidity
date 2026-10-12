#!/usr/bin/env python3
"""Stage 6, candidates A and B (`docs/stages/stage-6.md`): real-time deployable liquidity and its eligibility.

    PYTHONPATH=src python3 scripts/stage6_ab.py a      # the curve's bend
    PYTHONPATH=src python3 scripts/stage6_ab.py b      # the latent buffer, re-identified

Panel version 3, rebuilt to its manifest. Refits as Stage 3c's: the first on 2020-03-13 (the first episode's last day),
then every 21 observation days, to 2025-12-31. Refit k serves the days after its cutoff, up to the next refit's cutoff.

For every served day the record keeps the buffer a forecast reads, deployable liquidity (the as-of reserves ratio minus
the buffer) and its 90% interval, all in shares of bank assets. It then applies the plan's eligibility rules:
1. stability, the gap between refit k and k - 1 on each day k serves, under 0.5 points;
2. intervals, with a median width under 3 points;
3. the account of the distribution across the three H.8 bank groups. It cannot be computed until the group inputs
   exist (candidate C's prerequisite), so eligibility is recorded as pending, never assumed.

Beside these, it records the deciding score: the area under the ROC curve of deployable liquidity against the declared
material-use days (`fed_repo_material_use`), on served days from 2019-09-17, with the 2021-on split reported only.
Writes `results/stage6/{a,b}.json`. Nothing is published.
"""

import importlib.util
import json
import multiprocessing
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from repo_liquidity import anchored, demand_curve, deployable, latent

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "stage6"
REFIT_EVERY = 21


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _setup():
    pass_module = _load("stage4_curve_pass", ROOT / "scripts" / "stage4_curve_pass.py")
    s3b = _load("stage3b", ROOT / "scripts" / "stage3b_anchored.py")
    rows, manifest = pass_module.load_rows()
    rows = [row for row in rows if row.date <= demand_curve.LAST_DAY]
    anchor, stage2_sha = anchored.load_anchor()
    observations = deployable.assemble_b(rows)
    days = [o.day for o in observations]
    first = days.index(anchor.last_day)
    cutoffs = list(range(first, len(observations), REFIT_EVERY))
    labels = {row.date: row.values.get("fed_repo_material_use") for row in rows}
    return pass_module, s3b, rows, manifest, anchor, stage2_sha, observations, days, cutoffs, labels


def _served(cutoffs, k, n):
    """The observation indices refit k serves: after its cutoff, to the next refit's cutoff (the first serves its own
    cutoff day onward)."""
    start = cutoffs[k] + 1
    end = cutoffs[k + 1] if k + 1 < len(cutoffs) else n - 1
    return range(start, end + 1)


def _score(path, labels):
    """The deciding score, and the 2021-on split, on served days with a declared label."""
    def area(first):
        pairs = [(entry["deployable"], int(labels[date.fromisoformat(day)])) for day, entry in path.items()
                 if date.fromisoformat(day) >= first and labels.get(date.fromisoformat(day)) is not None]
        return {"auc": deployable.auc([p for p, _ in pairs], [y for _, y in pairs]),
                "days": len(pairs), "events": sum(y for _, y in pairs)}
    return {"from_2019_09_17": area(deployable.EVENTS_FROM), "from_2021_reported_only": area(deployable.FACILITY_ERA)}


def _record(name, what, settings, path, gaps, setup, extra):
    pass_module, _s3b, _rows, manifest, *_ = setup
    labels = setup[-1]
    stable = deployable.stability(gaps)
    width = deployable.widths((entry["deployable_lower"], entry["deployable_upper"]) for entry in path.values())
    document = {
        "stage": f"6, candidate {name.upper()}",
        "what": what,
        "settings": settings,
        "eligibility": {
            "stability": stable,
            "intervals": width,
            "distribution_account": {"computed": False,
                                     "why": "needs the H.8 bank-group inputs, candidate C's prerequisite; not built yet"},
            "eligible": None if stable["shown"] and width["shown"] else False,
            "note": ("eligible stays None (pending) until the distribution account is computed, and becomes False "
                     "as soon as rule 1 or 2 fails"),
        },
        "score": _score(path, labels),
        **extra,
        "path": path,
        "provenance": pass_module.provenance(manifest),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(document, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: document[key] for key in ("eligibility", "score")}, indent=1, default=str)[:3000])


def run_a():
    setup = _setup()
    _p, _s, rows, _m, anchor, stage2_sha, observations, days, cutoffs, _labels = setup
    sample = deployable.sample_a(rows)
    by_day = {row.day: row for row in sample}
    estimates, cache, path, gaps = [], {}, {}, {}
    for k, index in enumerate(cutoffs):
        cutoff = days[index]
        seen = [row for row in sample if row.day <= cutoff]
        key = None
        first, second = demand_curve.EPISODES
        ep2 = deployable.episode_days(seen, second)
        if sum(row.x < demand_curve.SCARCE_BELOW for row in ep2) < demand_curve.MIN_SCARCE_DAYS_REVISED:
            key = "first episode"  # the first episode's days are all before the first cutoff: one estimate serves
        estimate = cache.get(key) if key else None
        if estimate is None:
            estimate = deployable.bend_at(sample, cutoff=cutoff)
            if key:
                cache[key] = estimate
        estimates.append((cutoff, estimate))
        for i in _served(cutoffs, k, len(observations)):
            day = days[i]
            if day not in by_day:
                continue
            x = by_day[day].x
            path[day.isoformat()] = {"refit": cutoff.isoformat(), "episode": estimate.episode,
                                     "buffer": estimate.bend, "x": x, "deployable": x - estimate.bend,
                                     "deployable_lower": x - estimate.upper, "deployable_upper": x - estimate.lower}
            if k > 0:
                gaps[day.isoformat()] = abs(estimate.bend - estimates[k - 1][1].bend)
        print(f"A refit {k + 1}/{len(cutoffs)} {cutoff} {estimate.episode} bend {estimate.bend}", flush=True)
    switch = next(((c.isoformat(), e.bend) for c, e in estimates if e.episode == demand_curve.EPISODES[1][0]), None)
    _record("a", "The curve's bend, fitted on scarce-episode days only; one break between the episodes.",
            {"episodes": [[label, first.isoformat(), last.isoformat()] for label, first, last in demand_curve.EPISODES],
             "min_scarce_days": demand_curve.MIN_SCARCE_DAYS_REVISED, "scarce_below": demand_curve.SCARCE_BELOW,
             "bootstrap": {"block": demand_curve.BLOCK_LENGTH, "replications": demand_curve.REPLICATIONS,
                           "level": demand_curve.LEVEL},
             "refit_every": REFIT_EVERY, "first_refit": days[cutoffs[0]].isoformat()},
            path, gaps, setup,
            {"break": {"date": None,
                       "why": ("not identified: the bend is fitted on the two episodes' days only, so every date "
                               "between them splits the data the same way; the second episode's bend takes over at "
                               "the first refit at which that episode counts"),
                       "first_refit_on_the_second_episode": switch},
             "refits": [{"cutoff": c.isoformat(), "episode": e.episode, "bend": e.bend, "lower": e.lower,
                         "upper": e.upper, "days": e.days, "scarce_days": e.scarce_days} for c, e in estimates]})


def _checkpoint_path():
    return RESULTS / "b_checkpoint.jsonl"


def _load_checkpoint(commit):
    """Refits already fitted, from the checkpoint; refused if it was written by code that decides a figure differently.

    The test is the publish rule's (`docs/decisions/publish-rule.md`): nothing under `src/`, `metadata/` or
    `tests/fixtures/` changed between the commit that wrote an entry and `commit`.

    Raises:
        ValueError: if such a path changed.
    """
    import subprocess

    path = _checkpoint_path()
    if not path.exists():
        return {}
    done, checked = {}, set()
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["commit"] not in checked:
            changed = subprocess.run(["git", "diff", "--name-only", entry["commit"], commit, "--", "src", "metadata",
                                      "tests/fixtures"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            if changed.strip():
                raise ValueError(f"{path} was written at {entry['commit']}, and {changed.split()} changed since; "
                                 f"delete it to start again")
            checked.add(entry["commit"])
        done[entry["cutoff"]] = entry
    return done


def _fit_from(entry, key):
    if entry[key] is None:
        return None
    raw = entry[key]
    return deployable.FitB(tuple(raw["params"]), raw["loglike"], raw["converged"], date.fromisoformat(entry["cutoff"]),
                           tuple(date.fromisoformat(d) for d in raw["jump_days"]))


def _fit_to(fit):
    return None if fit is None else {"params": list(fit.params), "loglike": fit.loglike, "converged": fit.converged,
                                     "jump_days": [d.isoformat() for d in fit.jump_days]}


def run_b(pool):
    setup = _setup()
    pass_module, s3b, rows, manifest, anchor, stage2_sha, observations, days, cutoffs, _labels = setup
    commit = pass_module.provenance(manifest)["commit"]
    if pass_module.provenance(manifest)["tree_modified"]:
        raise ValueError("B's checkpoint is written only from a clean tree")
    done = _load_checkpoint(commit)
    reforms = latent.jump_days(observations, s3b.REFORMS)
    refits, path, gaps = [], {}, {}
    previous = {"reform": None, "break": None}
    for k, index in enumerate(cutoffs):
        cutoff = days[index]
        entry = done.get(cutoff.isoformat())
        if entry is None:
            seen = observations[: index + 1]
            reform_days = [d for d in reforms if d <= cutoff]
            fit_reform = deployable.fit_best_b(seen, anchor=anchor, jump_days=reform_days, cutoff=cutoff,
                                               previous=previous["reform"], mapper=pool.map)
            candidates = [(when, latent.jump_days(observations, [when])) for when in deployable.break_grid(cutoff)]
            candidates = [(when, [d for d in jd if d <= cutoff]) for when, jd in candidates]
            candidates = [(when, jd) for when, jd in candidates if jd]
            fit_break, break_when = None, None
            if candidates:
                data_start = deployable.start_grid_b(seen, anchor)[:1]
                jobs = [(list(seen), dict(anchor=anchor, jump_days=jd, cutoff=cutoff, start=data_start[0][1]))
                        for _when, jd in candidates]
                profile = list(pool.map(deployable._fit_b_job, jobs))
                best = max(range(len(profile)), key=lambda i: profile[i].loglike)
                break_when, break_days = candidates[best]
                fit_break = deployable.fit_best_b(seen, anchor=anchor, jump_days=break_days, cutoff=cutoff,
                                                  previous=previous["break"], mapper=pool.map)
            entry = {"commit": commit, "cutoff": cutoff.isoformat(), "reform": _fit_to(fit_reform),
                     "break": _fit_to(fit_break), "break_when": None if break_when is None else break_when.isoformat()}
            RESULTS.mkdir(parents=True, exist_ok=True)
            with _checkpoint_path().open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
        fit_reform, fit_break = _fit_from(entry, "reform"), _fit_from(entry, "break")
        break_when = None if entry["break_when"] is None else date.fromisoformat(entry["break_when"])
        previous["reform"] = fit_reform.params
        if fit_break is not None:
            previous["break"] = fit_break.params
        chosen = fit_reform if fit_break is None or fit_break.loglike <= fit_reform.loglike else fit_break
        kind = "reform dates" if chosen is fit_reform else f"one break at {break_when}"
        refits.append({"cutoff": cutoff, "fit": chosen, "kind": kind,
                       "loglike_reform": fit_reform.loglike,
                       "loglike_break": None if fit_break is None else fit_break.loglike,
                       "break_when": break_when, "converged": chosen.converged})
        print(f"B refit {k + 1}/{len(cutoffs)} {cutoff} {kind} converged={chosen.converged}", flush=True)
    for k, index in enumerate(cutoffs):
        cutoff, chosen, kind = refits[k]["cutoff"], refits[k]["fit"], refits[k]["kind"]
        served = _served(cutoffs, k, len(observations))
        end = served[-1] if len(served) else index
        horizon = observations[: end + 1]
        jumps_now = list(chosen.jump_days) + ([d for d in reforms if d > cutoff] if kind == "reform dates" else [])
        states = deployable.filter_path_b(horizon, chosen.params, anchor=anchor, jump_days=jumps_now)
        old = None
        if k > 0:
            before = refits[k - 1]
            jumps_old = list(before["fit"].jump_days) + ([d for d in reforms if d > before["cutoff"]]
                                                          if before["kind"] == "reform dates" else [])
            old = deployable.filter_path_b(horizon, before["fit"].params, anchor=anchor, jump_days=jumps_old)
        for i in served:
            if i < 2:
                continue
            state = states[i - 2]
            sd = state.variance ** 0.5
            x = observations[i].x
            day = days[i].isoformat()
            lower_b, upper_b = state.mean - deployable.Z90 * sd, state.mean + deployable.Z90 * sd
            path[day] = {"refit": cutoff.isoformat(), "buffer": state.mean, "buffer_sd": sd, "x": x,
                         "deployable": x - state.mean, "deployable_lower": x - upper_b,
                         "deployable_upper": x - lower_b}
            if old is not None:
                gaps[day] = abs(state.mean - old[i - 2].mean)
    _record("b", ("The latent buffer: Stage 3b's filter with drift held at 0, jumps only at the reform dates or at "
                  "one break (the better likelihood), and the gap TGCR - ON RRP rate as a third head."),
            {"reforms": [d.isoformat() for d in s3b.REFORMS],
             "break_grid": "first day of each quarter, 2020 Q2 to 2024 Q4, up to the cutoff; profiled from the data "
                           "start, then refitted from every start at the best date",
             "starts": ["previous", "data"] + [f"buffer_{b}" for b in anchored.START_BUFFERS],
             "anchor": {"intercept": anchor.intercept, "slope": anchor.slope,
                        "last_day": anchor.last_day.isoformat(), "source_sha256": stage2_sha},
             "heads": list(deployable.HEADS_B), "refit_every": REFIT_EVERY,
             "first_refit": days[cutoffs[0]].isoformat(), "interval": "filter variance, normal 90%"},
            path, gaps, setup,
            {"refits": [{"cutoff": r["cutoff"].isoformat(), "kind": r["kind"], "converged": r["converged"],
                         "loglike_reform": r["loglike_reform"], "loglike_break": r["loglike_break"],
                         "break_when": None if r["break_when"] is None else r["break_when"].isoformat(),
                         "params": list(r["fit"].params)} for r in refits],
             "refits_converged": sum(r["converged"] for r in refits)})


def main(argv):
    warnings.simplefilter("ignore")
    if argv[1:] == ["a"]:
        run_a()
    elif argv[1:] == ["b"]:
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn"),
                                 initializer=warnings.simplefilter, initargs=("ignore",)) as pool:
            run_b(pool)
    else:
        raise SystemExit("usage: stage6_ab.py a|b")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
