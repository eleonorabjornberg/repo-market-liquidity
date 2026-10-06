import sys, tempfile, pickle, math, statistics as st
from pathlib import Path
sys.path.insert(0, "src")
from repo_liquidity import panel, latent
from repo_model.data import load_daily_panel
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "panel.csv"; panel.build(p); obs = latent.assemble(load_daily_panel(p))
pickle.dump(obs, open(sys.argv[1], "wb"))
print(len(obs), obs[0].day, obs[-1].day)
by = {}
for o in obs: by.setdefault(o.day.year, []).append(o)
print("year  x_med  corr_med  disp_med  logonrrp_med  onrrp$bn_med  srf_nonzero/srf_obs")
for y, os in sorted(by.items()):
    def med(i):
        v = [o.y[i] for o in os if o.y[i] is not None]; return round(st.median(v), 3) if v else None
    srf = [o.y[3] for o in os if o.y[3] is not None]
    print(y, round(st.median(o.x for o in os), 4), med(0), med(1), med(2), round(math.expm1(med(2)), 1), f"{sum(v > 0 for v in srf)}/{len(srf)}")
