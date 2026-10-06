# Stage 3 directive: the latent buffer

**Written 6 October 2026, before any Stage 3 model was fitted.** Design choices are Eleonora's of 6 October 2026
(relayed by the orchestrating session): a buffer that changes over time and may shift at the reform dates; observed
through the corridor position plus three other measures; jumps allowed at every reform date; an extended Kalman filter;
a stability bar of 0.5 points. Stage 2 (`results/stage2/demand_curve.json`) is the evidence it builds on: at the same
reserves ratio, SOFR sat higher in the corridor in 2025 than in 2018 to March 2020.

## The model

- **State:** the desired buffer `B_t`, in units of the reserves ratio (reserve balances over commercial-bank total
  assets). Deployable liquidity is `D_t = x_t - B_t`, where `x_t` is the ratio known at day t's decision instant
  (read through the parent's `asof.InformationRule`, as in Stage 2).
- **Transition:** `B_t = B_{t-1} + eta_t`, `eta_t ~ N(0, q)` each business day. On a reform date in
  `docs/decisions/reform-dates.md` the variance is `q + j`, so the buffer may jump there and only drifts elsewhere. In
  the development window (to 2025-12-31) that is 2021-03-31, 2021-07-29, 2023-03-12, 2023-07-12 and 2023-12-13; later
  dates apply in the live filter.
- **Scarcity:** `g_t = s * log(1 + exp((B_t - x_t) / s))`, a smooth version of `max(B_t - x_t, 0)`, with `s = 0.005`.
- **Four observation heads,** each `y_i,t = a_i + b_i * f_i(B_t) + e_i,t`, `e_i,t ~ N(0, r_i)`:
  1. the corridor position, (SOFR - ON RRP rate) / (IORB - ON RRP rate), with `f = g_t` (Stage 2's outcome);
  2. SOFR dispersion, 75th minus 25th percentile in bp, with `f = g_t`;
  3. ON RRP take-up, `log(1 + $bn)`, with `f = D_t` (excess cash parks at the floor when liquidity is plentiful);
  4. standing repo facility take-up, `log(1 + $bn)`, with `f = g_t`; missing before 2021-07-29.

  A missing observation is skipped by the filter, never filled.
- **Estimation:** an extended Kalman filter linearizes each head around the predicted state. Parameters (`q`, `j`,
  `a_i`, `b_i`, `r_i`, the initial buffer) by maximum likelihood with statsmodels (`GenericLikelihoodModel`,
  approved in `docs/decisions/dependencies.md`).
- **Information:** the forecast for day T may use the filter through day T - 2, the last day whose SOFR, ON RRP and
  facility results are all public at T's decision instant (16:00 on T - 1). Filtered estimates only, never smoothed.
  Parameters are refitted every 21 business days on the data available at that refit's decision instant
  (`asof.refit_blocks`), from 2018-04-17 to 2025-12-31; the parent's lockbox holds 2026.

## What Stage 3 must show (Eleonora, 6 October 2026)

1. **Stability.** For every date, the filtered buffer from one walk-forward refit and the next differs by less than
   **0.5 points** of the reserves ratio.
2. **The like-for-like benchmark.** The mean filtered buffer over 2025 minus its mean over 2018 to March 2020 is
   positive, with a 90% interval above 0. The interval combines the filter's own state variances (taken as perfectly
   correlated within each period, the conservative direction) and is stated in the record.
3. **Curve-form sensitivity (reported, as `PLAN.md` asks).** The same fit with `s = 0.002` and `s = 0.01`, and with
   jumps only at the two legal breaks (2021-03-31, 2023-03-12), reported beside the main result.

If 1 or 2 fails, the pull request says so plainly and the model is not frozen. If both hold, the declaration is frozen by
checksum and the daily log of Stage 5a can start, once Eleonora merges.

## Not in Stage 3

No forecast is scored (that is Stage 4, under `docs/decisions/evaluation.md`), nothing is published, and no input from
Stage 1b is used.
