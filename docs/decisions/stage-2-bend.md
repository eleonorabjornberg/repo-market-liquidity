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
