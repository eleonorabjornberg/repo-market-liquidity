"""Phase 3's declaration: an overlay on the parent's registry and feature map, never a copy of them.

`docs/decisions/input-declarations.md`: new inputs are declared here and checked by the parent's own validators.
"""

import json
import pathlib
import unittest

from repo_model import contract

from repo_liquidity import declaration

ROOT = pathlib.Path(__file__).resolve().parents[1]


class OverlayTests(unittest.TestCase):
    def test_the_overlay_passes_the_parent_validators(self):
        self.assertEqual(declaration.validate(), [])

    def test_overlay_ids_do_not_collide_with_the_parent(self):
        overlay = json.loads((ROOT / "metadata" / "sources_phase3.json").read_text())
        parent = declaration.parent_registry()
        self.assertFalse(set(overlay) & set(parent))

    def test_a_colliding_overlay_is_refused(self):
        parent = declaration.parent_registry()
        with self.assertRaises(ValueError):
            declaration.merge(parent, {"frb_h8": parent["frb_h8"]})

    def test_an_overlay_without_provenance_for_an_early_time_is_refused(self):
        overlay = json.loads((ROOT / "metadata" / "sources_phase3.json").read_text())
        del overlay["frb_h41_treasury"]["availability_provenance"]
        self.assertTrue(declaration.validate(overlay))

    def test_every_phase3_feature_names_a_declared_field(self):
        registry = declaration.registry()
        for feature, pairs in declaration.FIELDS.items():
            for source, field in pairs:
                self.assertIn(field, registry[source]["fields"], feature)


class SwapTests(unittest.TestCase):
    def test_the_swap_adds_phase3_features_and_restores_the_parent(self):
        before = (contract.FEATURE_FIELDS, contract.FEATURE_SOURCES)
        with declaration.phase3_declaration():
            for feature in declaration.FIELDS:
                self.assertIn(feature, contract.FEATURE_FIELDS)
                self.assertIn(feature, contract.FEATURE_SOURCES)
            self.assertEqual(contract.FEATURE_FIELDS["on_rrp"], contract.ON_RRP_OPERATION_RESULTS_FIELDS)
        self.assertIs(contract.FEATURE_FIELDS, before[0])
        self.assertIs(contract.FEATURE_SOURCES, before[1])

    def test_the_swap_restores_the_parent_after_an_error(self):
        before = contract.FEATURE_FIELDS
        with self.assertRaises(RuntimeError):
            with declaration.phase3_declaration():
                raise RuntimeError("boom")
        self.assertIs(contract.FEATURE_FIELDS, before)

    def test_phase3_features_are_absent_outside_the_swap(self):
        for feature in declaration.FIELDS:
            if feature in ("on_rrp",):
                continue
            self.assertNotIn(feature, contract.FEATURE_FIELDS)


if __name__ == "__main__":
    unittest.main()
