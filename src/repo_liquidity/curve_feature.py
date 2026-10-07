"""Stage 4: Stage 2's curve as one feature of the parent's published gbm (`docs/stages/stage-4.md`).

At each refit the broken stick of Stage 2's revised test (SOFR's corridor position against the reserves ratio known at
the day's decision instant) is fitted on the training rows only, with its slope held at or above 0 (Eleonora,
7 October 2026). Read at a day's as-of reserves ratio and converted with the IORB and ON RRP rates in force on that day
as announced by its decision instant, it gives one number, `curve_implied_spread_bp`: the SOFR - IORB the curve
implies, in basis points. The wrapper fitter adds it to the published gbm's regressors and changes nothing else.

A curve that cannot be fitted, or that lands on a slope of 0, raises `CurveFailure`. Nothing replaces it with a
default: the run stops for a diagnosis and Eleonora's remedy.

The panel's `iorb` is the realized rate, a constituent of the target, read at the anchor. The rate a forecast for T may
know is in force on T is a scheduled input, `iorb_in_force`, declared in `metadata/sources_stage4.json` and added in
memory from the parent's own table of implementation notes (`scheduled.load_iorb_rates`). The published panels do not
change.

Standard library only; the gbm is the parent's (`repo_model.ml`, the `ml` extra).
"""

from __future__ import annotations

import bisect
import functools
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from repo_liquidity import declaration, demand_curve, parent_root, scheduled

#: The panel version Stage 4 reads (`scripts/build_panel.py --version 3`).
PANEL_VERSION = 3
DECISION_TIME = time(16, 0)
LAST_DAY = date(2025, 12, 31)
#: The parent's published comparison record, read at the pin: the declaration model A reproduces.
PUBLISHED_RECORD = "docs/runs/compare_persistence_vs_gbm_conformal_pid_nested_funding_crps.json"
MINIMUM_HISTORY = 61
REFIT_EVERY = 21
#: The published gbm's nine features, as its record lists them.
PUBLISHED_FEATURES = ("reserve_balances", "sofr_p25", "sofr_p75", "sofr_volume", "spread_bps", "tbill_13w",
                      "tbill_4w", "tga", "treasury_settlement")

FEATURE = "curve_implied_spread_bp"
IORB_COLUMN = scheduled.IORB_COLUMN
#: What the feature is computed from on a row: the reserves ratio's two parts and the corridor's two edges.
CURVE_INPUTS = ("reserve_balances", "bank_total_assets", "on_rrp_rate", IORB_COLUMN)
#: Everything the curve reads, for the parent's declaration check. The curve's labels are SOFR and IORB on training
#: days, the constituents of `spread_bps`, the target every model reads.
CURVE_READS = CURVE_INPUTS + ("spread_bps",)
#: Model B's declaration: the published nine plus every input the curve reads that they do not already include.
DECLARED_FEATURES = PUBLISHED_FEATURES + tuple(name for name in CURVE_INPUTS if name not in PUBLISHED_FEATURES)

STAGE4_OVERLAY = Path(__file__).resolve().parents[2] / "metadata" / "sources_stage4.json"
STAGE4_FIELDS = MappingProxyType({IORB_COLUMN: (("fed_iorb_rate", IORB_COLUMN),)})


class CurveFailure(ValueError):
    """A refit's curve could not be fitted, or carries no reserves signal (slope 0). Never replaced by a default."""


# -- the declaration ---------------------------------------------------------------------------------------------


def overlay() -> Dict[str, Mapping]:
    return json.loads(STAGE4_OVERLAY.read_text(encoding="utf-8"))


def registry() -> Dict[str, Mapping]:
    """Phase 3's registry plus Stage 4's scheduled IORB."""
    return declaration.merge(declaration.registry(), overlay())


def validate_overlay() -> List[str]:
    return declaration.validate(overlay())


@contextmanager
def stage4_declaration():
    """Phase 3's declaration, plus `iorb_in_force`, for the duration of the block."""
    from repo_model import contract

    with declaration.phase3_declaration():
        fields = MappingProxyType({**contract.FEATURE_FIELDS, **STAGE4_FIELDS})
        saved = contract.FEATURE_FIELDS, contract.FEATURE_SOURCES
        contract.FEATURE_FIELDS = fields
        contract.FEATURE_SOURCES = MappingProxyType(
            {feature: tuple(sorted({source for source, _field in pairs})) for feature, pairs in fields.items()})
        try:
            yield
        finally:
            contract.FEATURE_FIELDS, contract.FEATURE_SOURCES = saved


def with_stage4_columns(observations):
    """`observations` with `iorb_in_force` on every row, read at each row's decision instant.

    Raises:
        ValueError: if a row already carries the column.
    """
    from repo_model.data import DailyObservation

    clash = [row.date for row in observations if IORB_COLUMN in row.values]
    if clash:
        raise ValueError(f"{clash[0]} already carries {IORB_COLUMN}")
    dates = [row.date for row in observations]
    values = scheduled.iorb_in_force_values(dates, decision_time=DECISION_TIME)
    return [DailyObservation(row.date, {**row.values, IORB_COLUMN: value}) for row, value in zip(observations, values)]


def curve_rule(registry_: Optional[Mapping] = None, decision_time: time = DECISION_TIME):
    """The as-of rule the curve's inputs are read under. Use inside `stage4_declaration()`."""
    from repo_model.asof import InformationRule

    return InformationRule(registry() if registry_ is None else registry_, CURVE_INPUTS, decision_time=decision_time)


# -- the curve --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Curve:
    """SOFR's corridor position against the reserves ratio: flat above `kink`, rising with `slope` below it."""

    kink: float
    intercept: float
    slope: float

    def corridor_at(self, ratio: float) -> float:
        return self.intercept + self.slope * max(self.kink - ratio, 0.0)

    def implied_spread_bp(self, ratio: float, *, iorb: float, on_rrp_rate: float) -> float:
        """SOFR - IORB in basis points: position 1 is IORB, position 0 the ON RRP rate one corridor width below."""
        return 100.0 * (self.corridor_at(ratio) - 1.0) * (iorb - on_rrp_rate)


def fit_constrained(xs: Sequence[float], ys: Sequence[float], grid: Sequence[float] = demand_curve.GRID) -> Curve:
    """Stage 2's least-squares broken stick with the slope held at or above 0; ties go to the smaller kink.

    At each grid point the slope is `demand_curve.fit_broken_stick`'s, floored at 0, with the intercept refitted
    when the floor binds. Where every grid point's slope is positive this is Stage 2's fit exactly.

    Raises:
        CurveFailure: if no grid point leaves points on both sides of the kink, or if the best fit's slope is 0.
    """
    pairs = sorted(zip(xs, ys))
    n = len(pairs)
    px, pxx, py, pxy = [0.0], [0.0], [0.0], [0.0]
    for x, y in pairs:
        px.append(px[-1] + x)
        pxx.append(pxx[-1] + x * x)
        py.append(py[-1] + y)
        pxy.append(pxy[-1] + x * y)
    sorted_x = [x for x, _ in pairs]
    sy, syy = py[-1], sum(y * y for _, y in pairs)
    best: Optional[Tuple[float, float, float, float]] = None
    for k in grid:
        m = bisect.bisect_left(sorted_x, k)
        if m == 0 or m == n:
            continue
        sh = m * k - px[m]
        shh = m * k * k - 2 * k * px[m] + pxx[m]
        shy = k * py[m] - pxy[m]
        denominator = n * shh - sh * sh
        if denominator <= 0:
            continue
        b = (n * shy - sh * sy) / denominator
        if b < 0:
            b = 0.0
        a = (sy - b * sh) / n
        sse = syy - a * sy - b * shy
        if best is None or sse < best[3] - 1e-12:
            best = (k, a, b, sse)
    if best is None:
        raise CurveFailure(f"no grid point leaves points on both sides of the kink ({n} points)")
    kink, intercept, slope, _sse = best
    if slope <= 0:
        raise CurveFailure(f"the constrained fit's slope is 0 (bend {kink}): the curve carries no reserves signal")
    return Curve(kink=kink, intercept=intercept, slope=slope)


# -- the guards -------------------------------------------------------------------------------------------------


def require_on_or_before(days: Iterable[date], cutoff: date) -> None:
    """Raise unless every day the curve is fitted on is at or before the refit's cutoff.

    Raises:
        LookAheadError: naming the first later day.
    """
    from repo_model.splits import LookAheadError

    for day in days:
        if day > cutoff:
            raise LookAheadError(f"the curve for the refit at {cutoff} would be fitted on {day}, after its cutoff")


def require_as_of(info) -> None:
    """Raise unless every read behind a row's feature was public at that row's decision instant.

    An observed read must come from an earlier row; any read must be first observable by the decision instant.

    Raises:
        LookAheadError: naming the read.
    """
    from repo_model.asof import KIND_OBSERVED
    from repo_model.splits import LookAheadError

    for read in info.reads:
        if read.kind == KIND_OBSERVED and read.row >= info.scored_index:
            raise LookAheadError(f"{read.feature!r} is read at row {read.row}, not before the row it feeds "
                                 f"({info.scored_index})")
        if read.available_at is not None and read.available_at > info.decision_instant:
            raise LookAheadError(f"{read.feature!r} was first observable at {read.available_at}, after the "
                                 f"{info.decision_instant} decision")


# -- reading the curve on rows ----------------------------------------------------------------------------------


def _as_of_values(rows, rule, dates: Sequence[date], index: int) -> Optional[Mapping[str, Any]]:
    """The curve's inputs as public at `dates[index]`'s decision instant, or None when the rule has no read."""
    from repo_model.splits import SplitError

    if index < 1:
        return None
    try:
        info = rule.information_set(dates, index)
    except SplitError:
        return None
    rule.check(dates, info)
    require_as_of(info)
    return rule.observation(rows, info).values


def _ratio(values: Mapping[str, Any]) -> Optional[float]:
    reserves, assets = values.get("reserve_balances"), values.get("bank_total_assets")
    if reserves is None or assets is None or assets <= 0:
        return None
    return reserves / assets


def feature_value(curve: Curve, values: Mapping[str, Any]) -> Optional[float]:
    """The curve-implied spread from a row's as-of inputs; None if any input is missing."""
    ratio = _ratio(values)
    iorb, floor = values.get(IORB_COLUMN), values.get("on_rrp_rate")
    if ratio is None or iorb is None or floor is None:
        return None
    return curve.implied_spread_bp(ratio, iorb=iorb, on_rrp_rate=floor)


def curve_sample(rows, rule, *, cutoff: date) -> Tuple[List[float], List[float], List[date]]:
    """Each day's (ratio known at its decision instant, realized corridor position), for days at or before `cutoff`.

    The corridor position is Stage 2's (`demand_curve.corridor_position`), with the ON RRP rate in force on the day.
    """
    floors = scheduled.load_on_rrp_rates()
    dates = [row.date for row in rows]
    xs: List[float] = []
    ys: List[float] = []
    days: List[date] = []
    for index in range(len(rows)):
        if dates[index] > cutoff:
            break
        seen = _as_of_values(rows, rule, dates, index)
        if seen is None:
            continue
        ratio = _ratio(seen)
        today = rows[index].values
        floor = scheduled.rate_in_force(floors, dates[index])
        if ratio is None or today.get("sofr") is None or today.get("iorb") is None or floor is None:
            continue
        xs.append(ratio)
        ys.append(demand_curve.corridor_position(sofr=today["sofr"], iorb=today["iorb"], on_rrp_rate=floor))
        days.append(dates[index])
    require_on_or_before(days, cutoff)
    return xs, ys, days


def fit_curve(rows, rule, *, cutoff: date) -> Curve:
    """The refit's curve, on the days at or before `cutoff`.

    Raises:
        CurveFailure: as `fit_constrained`.
    """
    xs, ys, _days = curve_sample(rows, rule, cutoff=cutoff)
    return fit_constrained(xs, ys)


def with_training_feature(frame, rule, curve: Curve):
    """The training frame with the feature on each row: the curve at the inputs public at that row's decision."""
    from repo_model.data import DailyObservation

    dates = [row.date for row in frame]
    out = []
    for index, row in enumerate(frame):
        seen = _as_of_values(frame, rule, dates, index)
        value = None if seen is None else feature_value(curve, seen)
        out.append(DailyObservation(row.date, {**row.values, FEATURE: value}))
    return out


# -- the wrapper ------------------------------------------------------------------------------------------------


def published_command(panel_path: str = "PANEL.csv", report: str = "OUT/crps.json") -> List[str]:
    """The parent's CRPS command (`scripts/final_test_preregistration.py`, `CRPS_COMMAND`), ending at 2025-12-31.

    The published record was scored to 2025-12-31 under the lockbox; the final test's own end date is later.
    """
    import importlib.util

    path = parent_root() / "scripts" / "final_test_preregistration.py"
    spec = importlib.util.spec_from_file_location("_final_test_preregistration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    argv = list(module.CRPS_COMMAND)
    argv[1] = panel_path
    argv[argv.index("--end") + 1] = LAST_DAY.isoformat()
    argv[argv.index("--report") + 1] = report
    return argv


def published_arm(side: str = "b", splits: Optional[Path] = None):
    """The published gbm's fitter and its online calibration factory, built by the parent's own `compare` code.

    Returns:
        `(fitter, online_factory)`: a `functools.partial` of `ml.fit_gradient_boosted_quantiles` and the nested
        conformal PID factory, exactly as `compare` builds them from `published_command()`.
    """
    from repo_model import cli_eval
    from repo_model.cli import build_parser

    args = build_parser().parse_args(published_command())
    if splits is not None:
        args.splits = splits
    else:
        args.splits = parent_root() / "metadata" / "evaluation_splits.json"
    stripped, online = cli_eval._online_calibration(
        cli_eval._side(args, side), cli_eval.FITTER_FACTORIES.get(getattr(args, f"model_{side}")),
        splits=args.splits, refit_every=args.refit_every, side=f"-{side}")
    _name, fitter = cli_eval._select_fitter(stripped, side=f"-{side}")
    return fitter, online


def published_fitter():
    return published_arm()[0]


class CurveFeatureFitter:
    """Fits the curve on the fold's training frame, adds the feature, and calls the published fitter with it."""

    def __init__(self, base: functools.partial):
        keywords = dict(base.keywords)
        regressors = tuple(keywords.pop("regressors"))
        if FEATURE in regressors:
            raise ValueError(f"the published fitter already reads {FEATURE}")
        self.func = base.func
        self.regressors = regressors + (FEATURE,)
        self.settings = MappingProxyType(keywords)
        self.curves: List[Tuple[date, Curve]] = []

    def __call__(self, train_frame, *, minimum_history: int, information=None):
        if information is None:
            raise ValueError("the curve is read through the run's as-of rule; the fold loop must hand it over")
        rule = curve_rule(information.registry, information.decision_time)
        cutoff = train_frame[-1].date
        curve = fit_curve(train_frame, rule, cutoff=cutoff)
        self.curves.append((cutoff, curve))
        frame = with_training_feature(train_frame, rule, curve)
        inner = self.func(frame, regressors=self.regressors, minimum_history=minimum_history,
                          information=information, **self.settings)
        return CurveFeatureModel(inner, curve)


class CurveFeatureModel:
    """The published gbm, fitted with the feature, reading it off each feature row it is handed.

    A forecast's feature row is already as of its decision instant (`InformationRule.observation`), with the
    scheduled `on_rrp_rate` and `iorb_in_force` read at the scored day; the feature is computed from it. Every other
    attribute is the inner model's.
    """

    def __init__(self, inner, curve: Curve):
        self.inner = inner
        self.curve = curve

    @property
    def features_read(self) -> Tuple[str, ...]:
        inner = tuple(name for name in self.inner.features_read if name != FEATURE)
        return inner + tuple(name for name in CURVE_READS if name not in inner)

    def augment(self, row):
        from repo_model.data import DailyObservation

        if FEATURE in row.values:
            return row
        return DailyObservation(row.date, {**row.values, FEATURE: feature_value(self.curve, row.values)})

    def __getattr__(self, name: str):
        if name in ("inner", "curve"):
            raise AttributeError(name)
        attribute = getattr(self.inner, name)
        if name == "with_history":
            return lambda history, *args, **kwargs: CurveFeatureModel(attribute(history, *args, **kwargs), self.curve)
        if not callable(attribute):
            return attribute
        from repo_model.data import DailyObservation

        def call(*args, **kwargs):
            args = tuple(self.augment(arg) if isinstance(arg, DailyObservation) else arg for arg in args)
            kwargs = {key: self.augment(value) if isinstance(value, DailyObservation) else value
                      for key, value in kwargs.items()}
            return attribute(*args, **kwargs)

        return call
