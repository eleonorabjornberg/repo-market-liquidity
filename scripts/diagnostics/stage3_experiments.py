"""Stage 3 diagnostics: one experiment per call. Not the directive's model unless named baseline."""
import sys, pickle, json, math, warnings
from datetime import date
sys.path.insert(0, "src")
import numpy as np
from scipy.optimize import minimize
from repo_liquidity import latent
warnings.simplefilter("ignore")
REFORMS = [date(2021,3,31), date(2021,7,29), date(2023,3,12), date(2023,7,12), date(2023,12,13)]
P1 = (date(2018,4,17), date(2020,3,31)); P2 = (date(2025,1,1), date(2025,12,31))

def heads(obs, keep):
    return [latent.Observation(o.day, o.x, tuple(v if i in keep else None for i, v in enumerate(o.y))) for o in obs]

def fit(obs, fixed=None, b0=None):
    fixed = fixed or {}
    jumps = latent.jump_days(obs, REFORMS)
    start = list(latent.start_params(obs))
    if b0 is not None: start[0] = latent._logit(b0 / latent.BUFFER_MAX)
    free = [i for i in range(len(start)) if i not in fixed]
    def full(z):
        p = list(start)
        for k, i in enumerate(free): p[i] = z[k]
        for i, v in fixed.items(): p[i] = v
        return p
    f = lambda z: -(lambda v: v if math.isfinite(v) else -1e12)(latent.loglike(obs, full(z), jump_days=jumps))
    z = np.array([start[i] for i in free])
    r = minimize(f, z, method="Nelder-Mead", options={"maxiter": 4000, "maxfev": 8000})
    r = minimize(f, r.x, method="BFGS", options={"maxiter": 400})
    p = full(r.x)
    path = latent.filter_path(obs, p, jump_days=jumps)
    return p, -r.fun, path

def mean(path, w):
    v = [s.mean for s in path if w[0] <= s.day <= w[1]]; return round(sum(v) / len(v), 4)

def report(p, ll, path):
    n = latent.natural(p)
    out = {"loglike": round(ll, 1), "b0": round(n[0], 4), "drift_sd": round(math.sqrt(n[1]), 5), "jump_sd": round(math.sqrt(n[2]), 4),
           "P1": mean(path, P1), "P2": mean(path, P2),
           "yearly": {y: mean(path, (date(y,1,1), date(y,12,31))) for y in range(2018, 2026)}}
    for i, h in enumerate(latent.HEADS):
        out[h] = [round(n[3+3*i], 3), round(n[4+3*i], 2), round(n[5+3*i], 4)]
    return out

def main():
    global obs_all, name
    obs_all = pickle.load(open(sys.argv[1], 'rb')); name = sys.argv[2]
    TINY_Q =  latent._logit(1e-6 / latent.DRIFT_SD_MAX)   # drift sd 1e-6: buffer constant between reform dates
    res = {}
    if name.startswith("starts"):
        for b0 in (0.05, 0.10, 0.15, 0.20):
            res[f"b0={b0}"] = report(*fit(obs_all, b0=b0))
    elif name == "no_onrrp":
        res = report(*fit(heads(obs_all, {0, 1, 3})))
    elif name == "corr_disp":
        res = report(*fit(heads(obs_all, {0, 1})))
    elif name == "corr_disp_steps":
        res = report(*fit(heads(obs_all, {0, 1}), fixed={1: TINY_Q}))
    elif name == "all_steps":
        res = report(*fit(obs_all, fixed={1: TINY_Q}))
    elif name.startswith("stab_"):
        # cheap stability proxy: the worst consecutive pair of the walk-forward, refitted fresh
        keep = {"stab_base": {0,1,2,3}, "stab_cd": {0,1}}[name]
        fixed = {}
        out = {}
        for cut in (date(2021,9,15), date(2021,10,15), date(2023,12,29), date(2025,12,31)):
            o = heads([x for x in obs_all if x.day <= cut], keep)
            p, ll, path = fit(o, fixed=fixed)
            out[str(cut)] = {s.day.isoformat(): s.mean for s in path}
        days = sorted(set(out["2021-09-15"]) & set(out["2021-10-15"]))
        a = max(abs(out["2021-09-15"][d] - out["2021-10-15"][d]) for d in days)
        days2 = sorted(set(out["2023-12-29"]) & set(out["2025-12-31"]))
        b = max(abs(out["2023-12-29"][d] - out["2025-12-31"][d]) for d in days2)
        res = {"worst_gap_2021-09-15_vs_2021-10-15": round(a, 4), "worst_gap_2023-12-29_vs_2025-12-31": round(b, 4)}
    print(name, json.dumps(res, indent=1))

if __name__ == '__main__':
    main()
