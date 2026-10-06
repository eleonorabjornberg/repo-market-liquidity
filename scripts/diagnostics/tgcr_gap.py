"""Diagnosis: does TGCR minus the ON RRP rate (Nicholas, question 12) add anything to Stage 3b's corridor position?

    PYTHONPATH=src python3 scripts/diagnostics/tgcr_gap.py

Algebra first: TGCR - RRP = (SOFR - RRP) + (TGCR - SOFR), and the corridor position is (SOFR - RRP) / (IORB - RRP).
So the gap repeats the corridor's numerator unless TGCR - SOFR moves on its own.
"""
import math, statistics as st, sys, tempfile
from pathlib import Path
from repo_liquidity import demand_curve, panel, scheduled
from repo_model.data import load_daily_panel

def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return num / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "panel.csv"; panel.build(p); rows = load_daily_panel(p)
by = {r.date: r.values for r in rows}
FLOORS = scheduled.load_on_rrp_rates()
recs = []
for d in demand_curve.sample(rows):
    v = by[d.day]
    if v.get("tgcr") is None:
        continue
    floor = scheduled.rate_in_force(FLOORS, d.day)
    width = (v["iorb"] - floor) * 100 if floor is not None else None
    sofr_rrp = d.corridor * width if width else None
    recs.append((d.day, d.ratio, d.corridor, 100 * (v["tgcr"] - v["sofr"]), sofr_rrp, width))
gap = [r[4] + r[3] for r in recs]
print("days", len(recs), recs[0][0], recs[-1][0])
print("TGCR - SOFR (bp): median", st.median(r[3] for r in recs), "p5/p95",
      sorted(r[3] for r in recs)[len(recs)//20], sorted(r[3] for r in recs)[-len(recs)//20])
print("corr(gap, SOFR - RRP) levels", round(corr(gap, [r[4] for r in recs]), 4))
print("corr(gap, corridor) levels", round(corr(gap, [r[2] for r in recs]), 4))
dg = [b - a for a, b in zip(gap, gap[1:])]; dc = [b[2] - a[2] for a, b in zip(recs, recs[1:])]
print("corr of daily changes (gap, corridor)", round(corr(dg, dc), 4))
for y in range(2018, 2026):
    ys = [(g, r) for g, r in zip(gap, recs) if r[0].year == y]
    if ys:
        print(y, "gap median bp", round(st.median(g for g, _ in ys), 2), "corridor median", round(st.median(r[2] for _, r in ys), 3),
              "TGCR-SOFR median", round(st.median(r[3] for _, r in ys), 2), "corr", round(corr([g for g, _ in ys], [r[2] for _, r in ys]), 3))
