"""A test helper: the parent's lockbox with its blind tier moved, to show a module reads the lockbox and keeps no copy."""

import contextlib
import json
import pathlib
import tempfile
from datetime import date, timedelta
from unittest import mock

from repo_model import lockbox


@contextlib.contextmanager
def moved_lockbox(blind_start: date):
    """Patch `repo_model.lockbox.DEFAULT_LOCKBOX` to the tracked declaration with the blind tier starting `blind_start`."""
    declaration = json.loads(lockbox.DEFAULT_LOCKBOX.read_text(encoding="utf-8"))
    near_blind, blind = declaration["tiers"]
    near_blind["end"] = (blind_start - timedelta(days=1)).isoformat()
    blind["start"] = blind_start.isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "lockbox.json"
        path.write_text(json.dumps(declaration), encoding="utf-8")
        with mock.patch.object(lockbox, "DEFAULT_LOCKBOX", path):
            yield


@contextlib.contextmanager
def reclosed_near_blind():
    """Patch `repo_model.lockbox.DEFAULT_LOCKBOX` to the tracked declaration with the near-blind tier locked again (not opened)."""
    declaration = json.loads(lockbox.DEFAULT_LOCKBOX.read_text(encoding="utf-8"))
    declaration["tiers"][0]["opened"] = None
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "lockbox.json"
        path.write_text(json.dumps(declaration), encoding="utf-8")
        with mock.patch.object(lockbox, "DEFAULT_LOCKBOX", path):
            yield
