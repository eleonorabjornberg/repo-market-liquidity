"""The development records of Stages 1 to 6, and where each is verified (L0, #21, option (a)).

Every record under `results/` and `metadata/` was made at parent pin `RECORD_PIN` and last checked, all together, by
the full suite at `RECORD_COMMIT` (`main` when L0 started, merged by Eleonora). From L0 on, this repository's pin moves
and the duplicates of the parent are deleted (`docs/decisions/deleted-duplicates.md`), so the head suite can no longer
rebuild them. `scripts/verify_records.py` runs the record commit's own suite, at its own pin, after checking that its
record files are these bytes; CI runs it as the `records` job. At head, `tests/test_records.py` checks only that the
files are byte-unchanged and name the pin they were made at.

No record is edited in place (CLAUDE.md). A record made after L0 is not listed here; it carries its own check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

#: `main` when L0 started: the last commit whose suite checked every record below, at `RECORD_PIN`.
RECORD_COMMIT = "a1685aca6dc289b38d0718f04446aeed20081a7b"
#: The parent pin every record was made at (the `parent_commit` each one stamps).
RECORD_PIN = "71ab387e5557cc9ecefb12d1b2bf21d086571388"
#: The Stage 4 freeze's declaration checksum, as pinned in `docs/decisions/stage-4-freeze.md`.
FREEZE_CHECKSUM = "9706d3976558da4380426b703554506fe1044a66df1e5b68b201f051e077528a"

#: Each record file's sha256 at `RECORD_COMMIT`.
RECORD_FILES = {
    "metadata/fomc_calendar.json": "5fc58d38cd41d1659221140da07d4ffab8062f2a2a02c15a81bee2a72599a1d5",
    "metadata/phase3_panel_manifest.json": "97b512479dad1fa51b52fc5a98f33d6c61deeb9ee9a978a03985a8f3937dd207",
    "metadata/phase3_panel_v2_manifest.json": "09098f71c638c0267cbce4b6db846438df501aa2c7608efecd5c3dd746ad83c2",
    "metadata/phase3_panel_v3_manifest.json": "80fe60c9b9a32488c711cb13f09d60bea6236fc64f7110331dd8af9934faa1ce",
    "metadata/sources_phase3.json": "c8690548717c24420b9cbf13bd43a29414fd61599ce18b5da1fca7ecc8541b14",
    "metadata/sources_stage4.json": "22d70952162a01e9d656d60a0e3a5adfccdbe55161f81fb319045215547726b2",
    "results/stage2/demand_curve.html": "0c99277558ba0b91d7303f598525a0a9d190c0ca68e7b4291379de5085fb20fc",
    "results/stage2/demand_curve.json": "961c18277de6116e30a775a169854586968a16de6d26cb80f0f8d018b5adb549",
    "results/stage3/latent.json": "8e345133fc9f034aa2209fb69fc6c333924005ceb12e179874a06b757eda1d8d",
    "results/stage3b/anchored.json": "016c44f7a2d64636df64958a35812a070e2555c94e543690bd60e1953fa6af8b",
    "results/stage3c/realtime.json": "9b0064fd1a9f56638980492c8fea2395ad7b13c8b37b1c2ce006f9888d7ccb04",
    "results/stage4/brier.json": "96abc5ea715d879a19eb3b81a41a524e3a8d419fdc515007431d3098768105b8",
    "results/stage4/comparison.json": "9cb7d6259447304eb3fa566ed2c1b2294c67364f097c688fed6c21efa4a3a09a",
    "results/stage4/curve_pass.json": "4b889428864418a55fb483492508b68558bdcc06c79e125514dbb2e5746e3167",
    "results/stage5a/replay.json": "2d5853010346a90830be590ef4522c47b61c8ee3188ac03ac0d42269760ffa08",
    "results/stage6/a.json": "ebe6a9dd9d99360bdff4889530f9c7ffd164f7b99821a639f6ef51a39d92c0b4",
    "results/stage6/b.json": "e0b0b2092d36e831180bbafd240a65d9045cfbce7c4b2ff919a3901a0bac3811",
    "results/stage6/b_checkpoint.jsonl": "cacf4c21c3a98bca1e7694e2ef117658594c705387901fd38f47635027c60ecf",
}

#: Records made after L0, each with the test file that checks it (L0's docstring: "a record made after L0 carries its own
#: check"). They are not byte-pinned to `RECORD_COMMIT`; their own tests recompute them against the parent's pin.
OWN_CHECK = {
    "results/h10/development.json": "tests/test_h10_step2.py",
    "results/h10/sensitivity_onrrp_interaction.json": "tests/test_h10_step3.py",
    "results/h10/sensitivity_onrrp_regimes.json": "tests/test_h10_regimes.py",
}


def changed(root: Path) -> List[str]:
    """The record files under `root` whose bytes are not the recorded ones, or that are missing."""
    out = []
    for path, digest in sorted(RECORD_FILES.items()):
        file = root / path
        if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            out.append(path)
    return out
