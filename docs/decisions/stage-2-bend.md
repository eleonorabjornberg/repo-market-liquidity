# Decision: what Stage 2 must show

**Status: decided by Eleonora, 6 October 2026. In force once this record merges.**

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), choosing the proposed rule of `PLAN.md` D2.

Stage 2 shows a bend stable enough to model, and Stage 3 is designed, only if **both** hold:

1. **Each regime agrees with the pooled estimate.** Every regime with enough days on the scarce side of the curve has a
   90% stationary-bootstrap interval for the bend's location that overlaps the pooled interval. "Enough days" is
   stated in the Stage 2 directive before the curve is computed.
2. **The pooled estimate is sharp.** The pooled 90% interval is narrower than the 11–14% range of reserves over bank
   assets spanned by the parent's sensitivity variants (`scarcity.SENSITIVITY_VARIANTS`).

If either fails, the Stage 2 pull request says so plainly, and Stage 3 is reconsidered before it is designed.

## Amendment: the revised test (post-hoc), 6 October 2026

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session): "Let's reconsider the 120 days then", "the
laws changed", "We need to get this stage right before phase 3", choosing three fixes from a written diagnosis.

**This test is post-hoc.** It was written after the rule above was computed and returned *not shown*
(`results/stage2/demand_curve.json`, PR #7). That verdict stands on record and is not replaced; this amendment adds a
second, labelled test. The diagnosis that led to it is in the same record.

**The diagnosis, in brief.** (1) When reserves are abundant, SOFR sits on the ON RRP rate, and the gap between that
rate and IORB was moved by the Fed (20 to 25 bp in 2018, 10 bp in 2020 to 2023, 15 bp from December 2024), so the flat
part of SOFR − IORB moves with administered rates, not reserves, and the broken stick's bend absorbs those moves.
(2) Calendar pressure days do not drive the result. (3) The window has two scarce episodes, not five regimes.
(4) The upward shift of the bend between the episodes appears under two functional forms; its exact level does not.

**The revised test.** All of it is fixed here, before it is computed:

1. **The outcome is SOFR's position in the corridor:** (SOFR − ON RRP rate) / (IORB − ON RRP rate) on day T, 0 on
   the floor and 1 at IORB. The ON RRP offering rate is a scheduled input read from the FOMC implementation notes, as
   the facility rate is. The regressor is unchanged: reserves over bank assets known at T's decision instant.
2. **Two episodes, not five regimes:** episode 1 runs from the window's start to 2020-03-13, the last business day
   before the FOMC's 15 March 2020 actions; episode 2 is calendar 2025. An episode counts with at least **60** days
   below 13% of bank assets.
3. **Shown** if both episodes count and each episode's bend has a 90% stationary-bootstrap interval narrower than 3
   points (10-day mean block, 2000 replications, as above).
4. **The shift** (episode 2's bend minus episode 1's) is reported with its own 90% interval, from independent
   stationary bootstraps of the two episodes. It is the input Stage 3 needs; it decides nothing here.

The broken-stick form, the grid and the window (to 2025-12-31) are unchanged.
