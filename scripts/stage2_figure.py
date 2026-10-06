#!/usr/bin/env python3
"""Draw Stage 2's figure: each day's spread against its reserves ratio, by regime, with the fitted bends.

    PYTHONPATH=src python3 scripts/stage2_figure.py

Reads `results/stage2/demand_curve.json` and recomputes the day sample (`demand_curve.sample`) from the Phase 3
panel; writes `results/stage2/demand_curve.html`, one self-contained page (light and dark, hover on every point,
a table of every fit). For Eleonora's review only: nothing here is published (`docs/decisions/publish-rule.md`).
"""

import html
import json
import sys
import tempfile
from pathlib import Path

from repo_liquidity import demand_curve as dc
from repo_liquidity import panel, parent_root

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "results" / "stage2" / "demand_curve.json"
PAGE = ROOT / "results" / "stage2" / "demand_curve.html"
LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]
W, H, L, R, T, B = 880, 460, 60, 20, 20, 50
X0, X1, Y0, Y1 = 0.07, 0.20, -20.0, 30.0


def sx(x):
    return L + (min(max(x, X0), X1) - X0) / (X1 - X0) * (W - L - R)


def sy(y):
    return T + (Y1 - min(max(y, Y0), Y1)) / (Y1 - Y0) * (H - T - B)


def main():
    from repo_model.data import load_daily_panel
    from repo_model.evaluation_splits import load_split_declaration

    record = json.loads(RECORD.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "panel.csv"
        panel.build(path)
        days = dc.sample(load_daily_panel(path))
    splits = load_split_declaration(parent_root() / "metadata" / "evaluation_splits.json")
    labels = [label for label in splits.regime_labels if label in record["regimes"]]

    parts = []
    for i in range(6):
        y = Y0 + i * (Y1 - Y0) / 5
        parts.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{sy(y):.1f}" y2="{sy(y):.1f}"/>'
                     f'<text class="axis" x="{L-8}" y="{sy(y)+4:.1f}" text-anchor="end">{y:+.0f}</text>')
    for i in range(14):
        x = X0 + i * 0.01
        parts.append(f'<text class="axis" x="{sx(x):.1f}" y="{H-B+18}" text-anchor="middle">{x*100:.0f}%</text>')
    parts.append(f'<line class="zero" x1="{L}" x2="{W-R}" y1="{sy(0):.1f}" y2="{sy(0):.1f}"/>')
    lo, hi = record["pooled"]["kink_interval_90"]
    parts.append(f'<rect class="band" x="{sx(lo):.1f}" y="{T}" width="{sx(hi)-sx(lo):.1f}" height="{H-T-B}"/>'
                 f'<text class="note" x="{sx(hi)+4:.1f}" y="{T+12}">pooled bend, 90% interval</text>')
    for d in days:
        slot = labels.index(splits.regime(d.day))
        title = html.escape(f"{d.day}: ratio {d.ratio*100:.2f}%, spread {d.spread_bp:+.0f} bp, {splits.regime(d.day)}")
        parts.append(f'<circle class="s{slot}" cx="{sx(d.ratio):.1f}" cy="{sy(d.spread_bp):.1f}" r="2.5">'
                     f'<title>{title}</title></circle>')
    for slot, label in enumerate(labels):
        fit = record["regimes"][label].get("fit")
        if not fit:
            continue
        k, a, b = fit["kink"], fit["intercept_bp"], fit["slope_bp_per_unit"]
        xs = [X0, k, X1]
        pts = " ".join(f"{sx(x):.1f},{sy(a + b * max(k - x, 0)):.1f}" for x in xs)
        parts.append(f'<polyline class="fit l{slot}" points="{pts}"/>')
    rev = record["revised_test"]
    cy0, cy1 = -0.5, 3.0

    def cy(y):
        return T + (cy1 - min(max(y, cy0), cy1)) / (cy1 - cy0) * (H - T - B)

    second = []
    for i in range(8):
        y = cy0 + i * 0.5
        second.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{cy(y):.1f}" y2="{cy(y):.1f}"/>'
                      f'<text class="axis" x="{L-8}" y="{cy(y)+4:.1f}" text-anchor="end">{y:.1f}</text>')
    for i in range(14):
        x = X0 + i * 0.01
        second.append(f'<text class="axis" x="{sx(x):.1f}" y="{H-B+18}" text-anchor="middle">{x*100:.0f}%</text>')
    for y, name in ((0, "floor (ON RRP rate)"), (1, "IORB")):
        second.append(f'<line class="zero" x1="{L}" x2="{W-R}" y1="{cy(y):.1f}" y2="{cy(y):.1f}"/>'
                      f'<text class="note" x="{W-R-4}" y="{cy(y)-4:.1f}" text-anchor="end">{name}</text>')
    episode_labels = [label for label, _, _ in dc.EPISODES]
    for slot, (label, start, end) in enumerate(dc.EPISODES):
        for d in days:
            if start <= d.day <= end and d.corridor is not None:
                title = html.escape(f"{d.day}: ratio {d.ratio*100:.2f}%, corridor position {d.corridor:.2f}")
                second.append(f'<circle class="s{slot}" cx="{sx(d.ratio):.1f}" cy="{cy(d.corridor):.1f}" r="2.5">'
                              f'<title>{title}</title></circle>')
        e = rev["episodes"][label]
        k, a, b = e["fit"]["kink"], e["fit"]["intercept"], e["fit"]["slope_per_unit"]
        lo, hi = e["ratio_range"]
        pts = " ".join(f"{sx(x):.1f},{cy(a + b * max(k - x, 0)):.1f}" for x in (lo, min(max(k, lo), hi), hi))
        second.append(f'<polyline class="fit l{slot}" points="{pts}"/>')
        ilo, ihi = e["kink_interval_90"]
        second.append(f'<rect class="band" x="{sx(ilo):.1f}" y="{T}" width="{sx(ihi)-sx(ilo):.1f}" height="{H-T-B}"/>')
    second_legend = "".join(
        f'<span class="key"><svg width="12" height="12"><circle class="s{i}" cx="6" cy="6" r="5"/></svg>'
        f'{html.escape(label)}: bend {rev["episodes"][label]["fit"]["kink"]*100:.2f}% '
        f'({rev["episodes"][label]["kink_interval_90"][0]*100:.2f}% to {rev["episodes"][label]["kink_interval_90"][1]*100:.2f}%)</span>'
        for i, label in enumerate(episode_labels))
    rv = rev["verdict"]
    shift = rev["shift"]
    legend = "".join(
        f'<span class="key"><svg width="12" height="12"><circle class="s{i}" cx="6" cy="6" r="5"/></svg>'
        f'{html.escape(label)}</span>' for i, label in enumerate(labels))
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{e['days']}</td><td>{e['scarce_days']}</td>"
        f"<td>{'' if not e.get('fit') else format(e['fit']['kink']*100, '.2f') + '%'}</td>"
        f"<td>{'' if not e.get('kink_interval_90') else '%.2f%% to %.2f%%' % tuple(v*100 for v in e['kink_interval_90'])}</td>"
        f"<td>{'reference' if name == 'pooled' else 'yes' if e['scarce_days'] >= dc.MIN_SCARCE_DAYS else 'no'}</td></tr>"
        for name, e in [("pooled", record["pooled"])] + list(record["regimes"].items()))
    v = record["verdict"]
    css_slots_l = "".join(f".s{i}{{fill:{c}}}.l{i}{{stroke:{c}}}" for i, c in enumerate(LIGHT))
    css_slots_d = "".join(f".s{i}{{fill:{c}}}.l{i}{{stroke:{c}}}" for i, c in enumerate(DARK))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Stage 2 demand curve</title>
<style>
:root{{--surface:#fcfcfb;--ink:#1a1a19;--muted:#6b6a63;--grid:#e6e5df;--band:rgba(42,120,214,.10)}}
@media (prefers-color-scheme: dark){{:root{{--surface:#1a1a19;--ink:#ffffff;--muted:#c3c2b7;--grid:#33332f;--band:rgba(57,135,229,.18)}}}}
body{{background:var(--surface);color:var(--ink);font:14px/1.5 system-ui,sans-serif;margin:0;padding:16px;max-width:920px}}
svg.chart{{width:100%;height:auto}} .grid{{stroke:var(--grid);stroke-width:1}} .zero{{stroke:var(--muted);stroke-width:1}}
.axis,.note{{fill:var(--muted);font-size:11px}} .band{{fill:var(--band)}} circle{{stroke:var(--surface);stroke-width:.5;opacity:.75}}
circle:hover{{opacity:1;stroke:var(--ink);stroke-width:1.5}} .fit{{fill:none;stroke-width:2}}
{css_slots_l} @media (prefers-color-scheme: dark){{{css_slots_d}}}
.key{{margin-right:14px;display:inline-flex;gap:4px;align-items:center}} table{{border-collapse:collapse;margin-top:12px}}
td,th{{padding:4px 10px;border-bottom:1px solid var(--grid);text-align:left}} .muted{{color:var(--muted)}}
</style></head><body>
<h1>Stage 2: the reserve demand curve</h1>
<h2>Decided rule: SOFR &minus; IORB, five regimes</h2>
<p class="muted">SOFR minus IORB (bp) on each day from {record['settings']['window'][0]} to {record['settings']['window'][1]},
against reserves over commercial-bank assets known at that day's 4 pm decision instant. Lines: each regime's
broken-stick fit. Shaded: the pooled bend's 90% interval. Descriptive only; not published.</p>
<p><strong>Rule (docs/decisions/stage-2-bend.md): {'shown' if v['shown'] else 'not shown'}.</strong>
Eligible regimes (at least {dc.MIN_SCARCE_DAYS} days below 13%): {', '.join(v['eligible_regimes']) or 'none'};
not overlapping the pooled interval: {', '.join(v['non_overlapping']) or 'none'};
pooled interval width {v['pooled_width']*100:.2f} points ({'under' if v['pooled_sharp'] else 'not under'} 3).</p>
<div>{legend}</div>
<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Spread against reserves ratio by regime">
{''.join(parts)}
<text class="axis" x="{(W+L)/2}" y="{H-8}" text-anchor="middle">reserves / bank assets</text>
<text class="axis" x="14" y="{T+(H-T-B)/2}" transform="rotate(-90 14 {T+(H-T-B)/2})" text-anchor="middle">SOFR - IORB, bp</text>
</svg>
<p class="muted">Spreads outside {Y0:+.0f} to {Y1:+.0f} bp are drawn at the edge. Hover a point for its date.</p>
<h2>Revised test (post-hoc): SOFR measured from the floor, two scarce episodes</h2>
<p class="muted">Outcome: (SOFR &minus; ON RRP rate) / (IORB &minus; ON RRP rate), 0 on the floor and 1 at IORB.
Written in docs/decisions/stage-2-bend.md (amendment of 6 October 2026) after the decided rule returned not shown.
Shaded: each episode's 90% interval for its bend; each line is drawn only over the ratios its episode saw.</p>
<p><strong>Revised rule: {'shown' if rv['shown'] else 'not shown'} (post-hoc).</strong>
Shift of the bend, 2025 minus 2018&ndash;March 2020: {shift['point']*100:+.2f} points
(90% interval {shift['interval_90'][0]*100:+.2f} to {shift['interval_90'][1]*100:+.2f}).
The two episodes' ratio ranges overlap only from {max(rev['episodes'][episode_labels[0]]['ratio_range'][0], rev['episodes'][episode_labels[1]]['ratio_range'][0])*100:.1f}%
to {min(rev['episodes'][episode_labels[0]]['ratio_range'][1], rev['episodes'][episode_labels[1]]['ratio_range'][1])*100:.1f}%,
so each bend is found inside its own episode's range. <strong>The two bends mark different features</strong>: in
2018&ndash;March 2020 SOFR sat at about IORB and the bend is where it rises above it; in 2025 SOFR sat mid-corridor and the
bend is where it rises toward IORB. The like-for-like comparison is at the same ratio, in the shared band
{rev['same_ratio_comparison']['ratio_band'][0]*100:.1f}% to {rev['same_ratio_comparison']['ratio_band'][1]*100:.1f}%:
median corridor position {rev['same_ratio_comparison']['median_position'][0]:.2f} then
{rev['same_ratio_comparison']['median_position'][1]:.2f}, a difference of {rev['same_ratio_comparison']['difference']:+.2f}
(90% interval {rev['same_ratio_comparison']['difference_interval_90'][0]:+.2f} to {rev['same_ratio_comparison']['difference_interval_90'][1]:+.2f});
SOFR at or above IORB on {rev['same_ratio_comparison']['share_at_or_above_iorb'][0]:.0%} of those days then,
{rev['same_ratio_comparison']['share_at_or_above_iorb'][1]:.0%} in 2025.</p>
<div>{second_legend}</div>
<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Corridor position against reserves ratio, two episodes">
{''.join(second)}
<text class="axis" x="{(W+L)/2}" y="{H-8}" text-anchor="middle">reserves / bank assets</text>
<text class="axis" x="14" y="{T+(H-T-B)/2}" transform="rotate(-90 14 {T+(H-T-B)/2})" text-anchor="middle">corridor position</text>
</svg>
<h2>All fits</h2>
<table><tr><th>Sample</th><th>Days</th><th>Days below 13%</th><th>Bend</th><th>90% interval</th><th>Counts in test</th></tr>{rows}</table>
</body></html>
"""
    PAGE.write_text(page, encoding="utf-8")
    print(PAGE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
