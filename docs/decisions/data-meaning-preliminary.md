# Decision: data meaning for Stage 1, questions 1 to 3 (preliminary)

**Superseded by `data-meaning.md` (Nicholas Beroud, 6 October 2026), which corrects answers 1 and 5 and confirms 2 to 4.**

**Status: a PRELIMINARY ruling by Eleonora, 6 October 2026, pending Nicholas Beroud.** Under the parent's `PLAN.md`
the choice of data and its meaning is Nicholas's. This record lets Stage 1 be planned against a stated answer. It
becomes final when he confirms it on issue #1, and is replaced if he corrects it; his answer is recorded here either
way. Questions 4 and 5 were ruled on the same day (below); questions 6 to 11 on issue #1 are not ruled here.

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), choosing the recommended option on each.

## 1. The QE/QT measure: the realized weekly change, plus the announced caps

- **The realized weekly change in the Fed's Treasury holdings** is the flow that drains or adds reserves in the Stage 3
  transition. It is read from the H.4.1 release (as of Wednesday, published Thursday at 4:30 pm New York time), with an
  availability declaration and leakage test under the parent's information-set rule. It also captures the Fed's bill
  purchases since QT ended.
- **The announced runoff caps** enter as the expected pace (question 3).
- **The level of holdings is not an input.** It trends, and adds nothing beyond reserves, which the model already reads.

## 2. The proxies: yes, plus the distance to the ceiling

- **H.8 total assets of commercial banks (first prints)** measure bank balance-sheet size, as the parent's scarcity
  ratio already uses (`contract.BANK_TOTAL_ASSETS_FIELDS`).
- **Standing repo facility usage** is kept as the facility's take-up. Because it is zero on most days, it is joined by
  **the distance from SOFR to the facility's minimum bid rate** (the ceiling), which is announced in advance and so a
  scheduled input.

## 3. The runoff caps: known in advance, from their announcement

- **Each cap is a scheduled input**, public from its FOMC statement or implementation note (2:00 pm New York time on
  the meeting day) and applied from the effective date that announcement states. Each announcement is recorded with
  its source, as the parent records its announced IORB changes (`fed_iorb_announcements`).
- **A cap is read as a maximum pace**, not the realized one; the realized pace is question 1's weekly change.

## 4. ON RRP: the New York Fed's operation results

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), choosing the recommended option.

- ON RRP is read from the Desk's daily operation results (the parent's `nyfed_on_rrp`,
  `contract.ON_RRP_OPERATION_RESULTS_FIELDS`), public at 16:00 New York on the next business day. The parent's
  scarcity runs read the same source. FRED's `RRPONTSYD` stays refused: its latest vintage cannot be dated.

## 5. Standing repo facility usage before the facility: missing

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), choosing the recommended option.

- Before 2021-07-29 there was no facility, so its usage and its rate are **missing**, never zero. Zero would tell a
  model that a ceiling existed and went unused.
