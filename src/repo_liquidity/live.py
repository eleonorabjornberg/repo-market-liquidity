"""Stage 5a: the daily log's guards (`docs/stages/stage-5a.md`).

- **The FOMC guard.** The frozen declaration reads IORB and the ON RRP rate from two tables extended after each FOMC
  by a reviewed pull request. A day whose decision instant follows a scheduled FOMC statement that either table does
  not yet cover is refused (`ValueError`), so a missed update is a visible refusal, never a stale rate. The scheduled
  statements are `metadata/fomc_calendar.json`, read from the Board's calendar page, saved as a fixture.
- **Development days are never logged.** The log starts after the development window (to 2025-12-31). Days before its
  schedule is turned on are not confirmatory; that is the scoring's rule, not a refusal here.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import List, Mapping, NamedTuple, Optional, Sequence

from repo_liquidity import scheduled

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = ROOT / "metadata" / "fomc_calendar.json"
CALENDAR_PAGE = ROOT / "tests" / "fixtures" / "snapshots" / "fomc_calendar" / "fomccalendars.htm.gz"
#: FOMC statements are released at 14:00 New York time, the time every rate-table row carries.
STATEMENT_TIME = time(14, 0)
#: The decision time of every Phase 3 run.
DECISION_TIME = time(16, 0)
#: The development window's last day (`docs/decisions/evaluation.md`).
LAST_DEVELOPMENT_DAY = date(2025, 12, 31)


class Statement(NamedTuple):
    meeting: str
    instant: datetime


def load_fomc_calendar() -> List[Statement]:
    """The scheduled FOMC statements, in order.

    Raises:
        ValueError: if the saved page does not match its manifest, or the calendar's time is not the statements'.
    """
    manifest = json.loads(CALENDAR_PAGE.with_name(CALENDAR_PAGE.name + ".manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(CALENDAR_PAGE.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        raise ValueError(f"{CALENDAR_PAGE.name} does not match its manifest ({digest} != {manifest['sha256']})")
    calendar = json.loads(CALENDAR.read_text(encoding="utf-8"))
    if time.fromisoformat(calendar["statement_time"]) != STATEMENT_TIME or calendar["timezone"] != "America/New_York":
        raise ValueError(f"{CALENDAR.name}: statements are at {STATEMENT_TIME} America/New_York")
    return [Statement(entry["meeting"], datetime.combine(date.fromisoformat(entry["statement_date"]), STATEMENT_TIME))
            for entry in calendar["statements"]]


def table_coverage() -> Mapping[str, datetime]:
    """The last announcement each rate table carries."""
    return {scheduled.IORB_RATE_TABLE.name: scheduled.load_iorb_rates()[-1].announced_at,
            scheduled.ON_RRP_RATE_TABLE.name: scheduled.load_on_rrp_rates()[-1].announced_at}


def require_tables_cover(decision_instant: datetime, tables: Mapping[str, datetime],
                         statements: Optional[Sequence[Statement]] = None) -> None:
    """Raise unless every rate table covers the latest scheduled statement made by `decision_instant`.

    Raises:
        ValueError: naming the statement and each table that does not yet carry it.
    """
    statements = load_fomc_calendar() if statements is None else statements
    made = [statement for statement in statements if statement.instant <= decision_instant]
    if not made:
        return
    statement = made[-1]
    behind = [name for name, last in sorted(tables.items()) if last < statement.instant]
    if behind:
        raise ValueError(f"the FOMC statement of {statement.meeting} ({statement.instant}) precedes the "
                         f"{decision_instant} decision, but {', '.join(behind)} do not yet carry it; extend the tables "
                         f"by a reviewed pull request before this day is logged")


def require_loggable(day: date) -> None:
    """Raise if `day` is in the development window.

    Raises:
        ValueError: for a day on or before `LAST_DEVELOPMENT_DAY`.
    """
    if day <= LAST_DEVELOPMENT_DAY:
        raise ValueError(f"{day} is in the development window (to {LAST_DEVELOPMENT_DAY}); the log never writes it")


# -- the forecast core --------------------------------------------------------------------------------------------

def declared_taus():
    """The parent's declared stress thresholds (+5, +10, +20, +50 bp), the family the development run scored."""
    from repo_model.data import load_stress_thresholds

    from repo_liquidity import parent_root

    return tuple(float(tau) for tau in
                 load_stress_thresholds(parent_root() / "metadata" / "stress_thresholds.json")["taus_bp"])


#: Columns a placeholder row may carry beyond the parent's: the two scheduled rates the curve converts with.
SCHEDULED_PLACEHOLDER_COLUMNS = ("on_rrp_rate", "iorb_in_force")


def parent_live():
    """The parent's `scripts/live_record.py` at the pin, imported by path."""
    import importlib.util

    from repo_liquidity import parent_root

    path = parent_root() / "scripts" / "live_record.py"
    spec = importlib.util.spec_from_file_location("parent_live_record", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_reads_on_real_rows(rows, rule, index: int, last_real: int, module=None) -> None:
    """The parent's placeholder guard, with the two scheduled rates also allowed on a placeholder.

    Raises:
        LookAheadError: if an observed read, or a read of a column a placeholder does not carry, lands on one.
    """
    module = parent_live() if module is None else module
    saved = module.PLACEHOLDER_COLUMNS
    module.PLACEHOLDER_COLUMNS = frozenset(saved) | frozenset(SCHEDULED_PLACEHOLDER_COLUMNS)
    try:
        module.require_reads_on_real_rows(rows, rule, index, last_real)
    finally:
        module.PLACEHOLDER_COLUMNS = saved


def forecast(rows, *, module=None) -> dict:
    """Both arms' forecasts of the last row, as the frozen declaration makes them, scoring nothing.

    The CRPS arms walk `paired_model_comparison`'s fold loop through the last row (the parent's `distribution_run`):
    model A, the published gbm with nested conformal PID; model B, the same with the curve-implied spread; and as-of
    persistence. The probability arms walk `rolling_exceedance_backtest`'s loop through it (the parent's
    `forecast_run`), with the two pressure-probability benchmarks. Use inside `curve_feature.stage4_declaration()`.

    Returns:
        A dict of quantiles (`levels`, `model_a`, `model_b`, `persistence`), probabilities at the declared thresholds for both arms and
        both benchmarks, model B's curve for the last row's refit block, and each arm's training end.
    """
    from repo_model.onset import LEAP_JUMP_BP

    from repo_liquidity import curve_feature

    module = parent_live() if module is None else module
    registry = curve_feature.registry()
    out: dict = {"distributions": {}, "probabilities": {}}

    def distribution(fit, features, online):
        return module.distribution_run(rows, fit=fit, features=features, online_calibration=online,
                                       registry=registry, horizon=1, minimum_history=curve_feature.MINIMUM_HISTORY,
                                       refit_every=curve_feature.REFIT_EVERY)

    fit_p, online_p = curve_feature.published_arm(side="a")
    fit_a, online_a = curve_feature.published_arm()
    base_b, online_b = curve_feature.published_arm()
    fit_b = curve_feature.CurveFeatureFitter(base_b)
    for name, fit, features, online in (("persistence", fit_p, ("spread_bps",), online_p),
                                        ("model_a", fit_a, curve_feature.PUBLISHED_FEATURES, online_a),
                                        ("model_b", fit_b, curve_feature.DECLARED_FEATURES, online_b)):
        levels, quantiles, _settings, train_end = distribution(fit, features, online)
        out["distributions"]["levels"] = levels
        out["distributions"][name] = {"quantiles_bps": quantiles, "train_end": train_end.isoformat()}

    def probabilities(predictor, name, features, online=None, leap=True):
        report = module.forecast_run(rows, predictor=predictor, model_name=name, features=features,
                                     registry=registry, taus=declared_taus(), horizon=1, online_calibration=online,
                                     leap_jump_bp=LEAP_JUMP_BP[1] if leap else None)
        return {f"+{tau:g}bp": report.forecast[-1][position] for position, tau in enumerate(report.taus)}

    name_a, predictor_a, online_ea, benchmarks = curve_feature.published_exceedance_arm()
    name_b, predictor_b, online_eb, _ = curve_feature.published_exceedance_arm(with_feature=True)
    out["probabilities"]["model_a"] = probabilities(predictor_a, name_a, curve_feature.PUBLISHED_FEATURES, online_ea)
    out["probabilities"]["model_b"] = probabilities(predictor_b, name_b, curve_feature.DECLARED_FEATURES, online_eb)
    for bench_name, features, bench in benchmarks:
        out["probabilities"][bench_name] = probabilities(bench, bench_name, features, leap=False)
    last = fit_b.curves[-1]
    out["curve"] = {"cutoff": last.cutoff.isoformat(), "kink": last.curve.kink, "intercept": last.curve.intercept,
                    "slope": last.curve.slope,
                    "carried_from": None if last.carried_from is None else last.carried_from.isoformat()}
    return out


# -- the record ---------------------------------------------------------------------------------------------------


class Written(NamedTuple):
    path: Path
    sha256: str


def record_path(out_dir: Path, day: date) -> Path:
    return Path(out_dir) / "live" / f"{day.isoformat()}.json"


def write_record(out_dir: Path, day: date, record: Mapping) -> Written:
    """Write `day`'s record once, as `live/YYYY-MM-DD.json`; never over an existing file.

    Raises:
        ValueError: if the record names another day, or `day` already has a record.
    """
    if record.get("decision_day") != day.isoformat():
        raise ValueError(f"the record names {record.get('decision_day')!r}, not {day}")
    path = record_path(out_dir, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, indent=1, sort_keys=True) + "\n").encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(payload)
    except FileExistsError:
        raise ValueError(f"{day} already has a record ({path}); a day is written once") from None
    return Written(path, hashlib.sha256(payload).hexdigest())
