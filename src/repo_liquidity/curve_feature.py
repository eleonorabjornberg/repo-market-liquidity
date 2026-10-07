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
memory from this repository's table of implementation notes, seeded from the parent's (`scheduled.load_iorb_rates`). The published panels do not
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
#: The parent's published exceedance record: the secondary Brier result's model A.
PUBLISHED_EXCEEDANCE_RECORD = "docs/runs/exceedance_gbm_conformal_pid_nested_funding.json"
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


@dataclass(frozen=True)
class RefitCurve:
    """The curve a refit used: fitted at `cutoff`, or carried from the refit at `carried_from` when its own failed."""

    cutoff: date
    curve: Curve
    carried_from: Optional[date]


def _refit_curve(curves: List[RefitCurve], train_frame, rule) -> Curve:
    """The refit's curve, recorded in `curves`: fitted on the frame, or carried from the latest fitted one.

    A second call at the same cutoff reuses that refit's curve. The carry is the curve-pass remedy (Eleonora,
    7 October 2026).

    Raises:
        CurveFailure: if the curve fails and no earlier refit fitted one.
        LookAheadError: if the carried curve was fitted after this refit's cutoff.
    """
    cutoff = train_frame[-1].date
    if curves and curves[-1].cutoff == cutoff:
        return curves[-1].curve
    try:
        curve, carried_from = fit_curve(train_frame, rule, cutoff=cutoff), None
    except CurveFailure:
        fitted = [entry for entry in curves if entry.carried_from is None]
        if not fitted:
            raise
        require_on_or_before([fitted[-1].cutoff], cutoff)
        curve, carried_from = fitted[-1].curve, fitted[-1].cutoff
    curves.append(RefitCurve(cutoff, curve, carried_from))
    return curve


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
        self.curves: List[RefitCurve] = []

    def __call__(self, train_frame, *, minimum_history: int, information=None):
        """One refit. A failed curve carries the last fitted one (the curve-pass remedy, Eleonora, 7 October 2026).

        Raises:
            CurveFailure: if the curve fails and no earlier refit fitted one.
            LookAheadError: if the carried curve was fitted after this refit's cutoff.
        """
        if information is None:
            raise ValueError("the curve is read through the run's as-of rule; the fold loop must hand it over")
        rule = curve_rule(information.registry, information.decision_time)
        curve = _refit_curve(self.curves, train_frame, rule)
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


class CurveFeatureExceedance:
    """The published gbm's exceedance predictor with the curve-implied spread: the secondary Brier result's model B.

    `inner` is `ml.gbm_exceedance` built with the published regressors plus `FEATURE` (`published_exceedance_arm`).
    Each call is one refit: the curve is fitted on the training rows (carried as `CurveFeatureFitter` carries it),
    the feature is added to the training rows as of each row's decision and to each feature row, and the curves'
    `features_read` report the curve's inputs in place of the feature, for the parent's declaration check.
    """

    def __init__(self, inner):
        self.inner = inner
        self.curves: List[RefitCurve] = []

    def __call__(self, train_rows, feature_rows, taus, information=None, histories=None, uncalibrated=False):
        import dataclasses

        if information is None:
            raise ValueError("the curve is read through the run's as-of rule; the fold loop must hand it over")
        rule = curve_rule(information.registry, information.decision_time)
        curve = _refit_curve(self.curves, train_rows, rule)
        model = CurveFeatureModel(None, curve)
        result = self.inner(with_training_feature(train_rows, rule, curve),
                            [model.augment(row) for row in feature_rows], taus,
                            information=information, histories=histories, uncalibrated=uncalibrated)
        inner_reads = tuple(name for name in result.features_read if name != FEATURE)
        return dataclasses.replace(
            result, features_read=inner_reads + tuple(name for name in CURVE_READS if name not in inner_reads))


def published_exceedance_command(panel_path: str = "PANEL.csv", report: str = "OUT/exceedance.json") -> List[str]:
    """The `exceedance-backtest` command behind the parent's published exceedance record, as its declaration states.

    `docs/runs/exceedance_gbm_conformal_pid_nested_funding.json` at the pin: the gbm with nested conformal PID, the
    published nine features, minimum history 61, refit every 21, decision 16:00, to 2025-12-31, the declared stress
    thresholds, and both pressure-probability benchmarks.
    """
    root = parent_root()
    argv = ["exceedance-backtest", "--panel", panel_path, "--thresholds",
            str(root / "metadata" / "stress_thresholds.json"), "--registry", str(root / "metadata" / "sources.json"),
            "--decision-time", "16:00", "--minimum-history", str(MINIMUM_HISTORY), "--refit-every",
            str(REFIT_EVERY), "--splits", str(root / "metadata" / "evaluation_splits.json"), "--end",
            LAST_DAY.isoformat(), "--model", "gbm", "--calibration", "conformal_pid_nested",
            "--benchmark", "calendar_climatology", "--benchmark", "persistence_logistic", "--report", report]
    for name in PUBLISHED_FEATURES:
        argv += ["--feature", name]
    return argv


def published_exceedance_arm(with_feature: bool = False):
    """The published exceedance predictor and its online calibration factory, built by the parent's own code.

    With `with_feature`, the same predictor built with `FEATURE` added to its regressors and wrapped in
    `CurveFeatureExceedance`; every setting is resolved by the same parent resolvers.

    Returns:
        `(name, predictor, online_factory, benchmarks)`, where `benchmarks` is the parent's
        `[(name, features, predictor)]` for the two pressure-probability benchmarks.
    """
    from repo_model import cli_eval
    from repo_model.cli import build_parser

    args = build_parser().parse_args(published_exceedance_command())
    model_args, online = cli_eval._online_calibration(
        args, cli_eval.MODEL_FACTORIES.get(args.model), splits=args.splits, refit_every=args.refit_every)
    benchmarks = cli_eval._benchmarks(args)
    if not with_feature:
        name, predictor = cli_eval._select_model(model_args, settings_flags=True)
        return name, predictor, online, benchmarks
    choice = cli_eval.MODEL_FACTORIES["gbm"]
    regressors, _regime = cli_eval._regressors_and_regime(model_args, "gbm", choice.needs_regime_variable)
    settings: Dict[str, Any] = {}
    settings.update(cli_eval._calibration(model_args, "gbm", choice.takes_calibration))
    settings.update(cli_eval._spread_change_lags(model_args, "gbm", choice.takes_spread_change_lags))
    settings.update(cli_eval._volatility_feature(model_args, "gbm", choice.takes_volatility_feature))
    settings.update(cli_eval._arx_feature(model_args, "gbm", choice.takes_arx_feature))
    settings.update(cli_eval._tail(model_args, "gbm", choice.takes_tail))
    inner = choice.construct(regressors=tuple(regressors) + (FEATURE,), regime_variable=None,
                             minimum_history=model_args.minimum_history, settings=settings)
    return "gbm_curve_implied_spread", CurveFeatureExceedance(inner), online, benchmarks
