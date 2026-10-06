# Decision: where Phase 3's new inputs are declared

**Status: decided by Eleonora, 6 October 2026. In force once this record merges.**

Ruling (Eleonora, 6 October 2026; relayed by the orchestrating session), choosing the recommended option of `PLAN.md` D1: "In this repo."

- **Phase 3's new inputs are declared and parsed in this repository**, not in the parent. Their availability
  declarations live in a registry overlay here, with this repository's parsers and tracked snapshots.
- **The overlay is checked by the parent's own validators** (`contract.validate_release_lag`,
  `asof.validate_scheduled_availability`, `registry.check_availability_provenance`) and read through the parent's
  as-of machinery (`asof.InformationRule`). Nothing of the parent is copied or re-implemented.
- **Why:** the parent's publish rule makes a record scored at commit R unpublishable once the parent's `src/`,
  `metadata/` or `tests/fixtures/snapshots/` change after R. Leaving the parent untouched keeps the final test's
  records (repo-market-model#151) publishable.
- Inputs the parent already declares (ON RRP operation results, H.8 first prints, standing repo facility usage) are
  switched on in Phase 3's own declaration, never in the parent's.
