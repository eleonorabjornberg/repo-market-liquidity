# Superseded: the H7m stage verdict as first published (#191)

`verdict.json` here is `results/h7/verdict.json` as merged in PR #191, kept byte for byte
(sha256 `15f26a39f89a34b1944ea550e1e8e571d42959a67185902d02e87cffc3a4bc65`).

It is superseded, not corrected. The only change is `sources.distribution_account.sha256`: this file pins the step-4 account as
first published (#174, sha256 `5b8ee596d16ccf6277f7174e109746c342bbfad270d10cfd9071fa9a8ebd20e8`), and #190 republished that
account without the withdrawn `Ag_*` rows (sha256 `f32e4c8433525071e150b2d43f030e43b22aa3961a9ecd6c6b118b5032bbf922`). The verdict,
the eligibility table and every estimator's status are unchanged; the withdrawn rows were never the reason for the verdict.
The record in `results/h7/` replaces it (directive #195).
