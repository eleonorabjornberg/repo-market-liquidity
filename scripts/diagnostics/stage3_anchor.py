import sys, pickle, math, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import stage3_experiments as exp
from repo_liquidity import latent
obs = pickle.load(open(sys.argv[1], "rb"))
a, b = float(sys.argv[2]), float(sys.argv[3])
heads = {0} if sys.argv[4] == "c" else {0, 1}
o = exp.heads(obs, heads)
p, ll, path = exp.fit(o, fixed={3: a, 4: math.log(b)})
r = exp.report(p, ll, path)
P = lambda w: [s for s in path if w[0] <= s.day <= w[1]]
sd = lambda ss: sum(math.sqrt(s.variance) for s in ss) / len(ss)
d = r["P2"] - r["P1"]; h = 1.645 * math.sqrt(sd(P(exp.P1)) ** 2 + sd(P(exp.P2)) ** 2)
print(sys.argv[2:], "ll", r["loglike"], "drift", r["drift_sd"], "jump", r["jump_sd"], "P1", r["P1"], "P2", r["P2"],
      "shift", round(d, 4), [round(d - h, 4), round(d + h, 4)], "yrs", list(r["yearly"].values()), "corr r", r["corridor_position"][2])
