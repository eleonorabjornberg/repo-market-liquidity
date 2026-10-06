"""Stage 2: the reserve demand curve, and where it bends (descriptive; nothing is forecast or scored).

The spread SOFR - IORB on day T against reserves over commercial-bank assets as known at T's decision instant
(16:00 on the panel day before T), read through the parent's as-of rule (`asof.InformationRule`). The bend is the
kink of a broken-stick fit, spread = a + b * max(k - ratio, 0): flat above k, rising as reserves fall below it. Its
90% interval comes from the parent's stationary bootstrap (`metrics.stationary_bootstrap_interval`).

What Stage 2 must show is decided in `docs/decisions/stage-2-bend.md`; the two thresholds it left to the directive
(120 business days on the scarce side, a 10-day mean block) are Eleonora's rulings of 6 October 2026. Window:
2018-04-03 to 2025-12-31, the parent's lockbox holding 2026. Standard library only.
"""

from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass
from datetime import date, time
from typing import Dict, List, Optional, Sequence, Tuple

#: The top of the parent's satiation band (`scarcity.SATIATION_BAND`): a day below it is on the scarce side.
SCARCE_BELOW = 0.13
#: A regime counts in the stability test with at least this many scarce-side days (ruling, 6 October 2026).
MIN_SCARCE_DAYS = 120
#: The pooled interval must be narrower than the parent's sensitivity range for the band, 11% to 14%.
SHARP_WIDTH = 0.14 - 0.11
BLOCK_LENGTH = 10
REPLICATIONS = 2000
LEVEL = 0.90
#: The grid the bend is searched on: reserves over bank assets from 6% to 22%, in steps of 0.05 points.
GRID = tuple(round(0.06 + 0.0005 * i, 4) for i in range(321))
LAST_DAY = date(2025, 12, 31)
DECISION_TIME = time(16, 0)


@dataclass(frozen=True)
class Fit:
    kink: float
    intercept: float
    slope: float
    sse: float


def fit_broken_stick(xs: Sequence[float], ys: Sequence[float], grid: Sequence[float] = GRID) -> Fit:
    """Least-squares broken stick over `grid`; ties go to the smaller kink.

    Raises:
        ValueError: if no grid point leaves points on both sides of the kink.
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
    best: Optional[Fit] = None
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
        a = (sy - b * sh) / n
        sse = syy - a * sy - b * shy
        if best is None or sse < best.sse - 1e-12:
            best = Fit(kink=k, intercept=a, slope=b, sse=sse)
    if best is None:
        raise ValueError("no kink on the grid has points on both sides")
    return best


def seed_for(label: str) -> int:
    return int(hashlib.sha256(f"repo-market-liquidity stage 2 {label}".encode()).hexdigest()[:8], 16)


def kink_interval(xs: Sequence[float], ys: Sequence[float], *, seed: int,
                  replications: int = REPLICATIONS) -> Tuple[float, float]:
    """The bend's 90% stationary-bootstrap interval; `xs` and `ys` in date order."""
    from repo_model.metrics import stationary_bootstrap_interval

    def statistic(indices):
        return fit_broken_stick([xs[i] for i in indices], [ys[i] for i in indices]).kink

    return stationary_bootstrap_interval(statistic, len(xs), block_length=BLOCK_LENGTH, seed=seed,
                                         replications=replications, level=LEVEL)


def scarce_days(xs: Sequence[float]) -> int:
    return sum(1 for x in xs if x < SCARCE_BELOW)


def _overlap(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def stability_verdict(*, pooled: Tuple[float, float], regimes: Dict[str, Tuple[float, float]]) -> Dict:
    """`docs/decisions/stage-2-bend.md`: every eligible regime overlaps the pooled interval, and it is sharp."""
    non_overlapping = sorted(label for label, interval in regimes.items() if not _overlap(interval, pooled))
    sharp = (pooled[1] - pooled[0]) < SHARP_WIDTH
    return {
        "eligible_regimes": sorted(regimes),
        "non_overlapping": non_overlapping,
        "pooled_width": pooled[1] - pooled[0],
        "pooled_sharp": sharp,
        "shown": bool(regimes) and not non_overlapping and sharp,
    }


def require_window(days: Sequence[date]) -> None:
    """Refuse any day the parent's lockbox holds (2026 on), and any day after 2025-12-31.

    Raises:
        LookAheadError: naming the first such day.
    """
    from repo_model.lockbox import require_unlocked
    from repo_model.splits import LookAheadError

    require_unlocked(days, where="Stage 2 demand curve")
    late = [day for day in days if day > LAST_DAY]
    if late:
        raise LookAheadError(f"Stage 2 reads no day after {LAST_DAY}; got {late[0]}")


@dataclass(frozen=True)
class Day:
    day: date
    ratio: float
    spread_bp: float
    p75_spread_bp: Optional[float]
    on_rrp_bn: Optional[float]


def sample(rows) -> List[Day]:
    """Each day's realized spread with the reserves ratio and ON RRP known at its decision instant.

    Rows after 2025-12-31 are dropped before anything is read; the rest pass `require_window`. A day whose as-of
    reads are incomplete is skipped.
    """
    from repo_model.asof import InformationRule
    from repo_model.splits import SplitError

    from repo_liquidity import declaration

    rows = [row for row in rows if row.date <= LAST_DAY]
    dates = [row.date for row in rows]
    require_window(dates)
    out = []
    with declaration.phase3_declaration():
        rule = InformationRule(declaration.registry(), ["reserve_balances", "bank_total_assets", "on_rrp"],
                               decision_time=DECISION_TIME)
        for index in range(len(rows)):
            try:
                info = rule.information_set(dates, index)
            except SplitError:
                continue
            rule.check(dates, info)
            seen = rule.observation(rows, info).values
            reserves, assets = seen.get("reserve_balances"), seen.get("bank_total_assets")
            if reserves is None or assets is None:
                continue
            today = rows[index].values
            if today.get("sofr") is None or today.get("iorb") is None:
                continue
            p75 = today.get("sofr_p75")
            out.append(Day(
                day=dates[index],
                ratio=reserves / assets,
                spread_bp=round(100.0 * (today["sofr"] - today["iorb"]), 6),
                p75_spread_bp=None if p75 is None else round(100.0 * (p75 - today["iorb"]), 6),
                on_rrp_bn=seen.get("on_rrp"),
            ))
    return out


def binned_curve(days: Sequence[Day], width: float = 0.01) -> List[Dict]:
    """The median spread in bins of the ratio, `width` wide."""
    bins: Dict[int, List[Day]] = {}
    for d in days:
        bins.setdefault(int(d.ratio // width), []).append(d)
    out = []
    for key in sorted(bins):
        group = bins[key]
        spreads = sorted(d.spread_bp for d in group)
        out.append({
            "ratio_from": round(key * width, 4),
            "ratio_to": round((key + 1) * width, 4),
            "days": len(group),
            "median_spread_bp": _median(spreads),
            "share_above_5bp": round(sum(1 for s in spreads if s > 5) / len(spreads), 4),
        })
    return out


def _median(values: Sequence[float]) -> float:
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def describe(days: Sequence[Day], label: str, *, replications: int = REPLICATIONS) -> Dict:
    xs = [d.ratio for d in days]
    ys = [d.spread_bp for d in days]
    entry = {
        "label": label,
        "first": days[0].day.isoformat() if days else None,
        "last": days[-1].day.isoformat() if days else None,
        "days": len(days),
        "scarce_days": scarce_days(xs),
        "ratio_range": [round(min(xs), 5), round(max(xs), 5)] if days else None,
    }
    try:
        fit = fit_broken_stick(xs, ys)
    except ValueError as error:
        entry["fit"] = None
        entry["note"] = str(error)
        return entry
    entry["fit"] = {"kink": fit.kink, "intercept_bp": round(fit.intercept, 6), "slope_bp_per_unit": round(fit.slope, 4)}
    entry["kink_interval_90"] = list(kink_interval(xs, ys, seed=seed_for(label), replications=replications))
    return entry
