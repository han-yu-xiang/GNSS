from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SourceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory_path = ROOT / "provenance/source_inventory.json"
        if not cls.inventory_path.is_file():
            raise AssertionError("run build_source_inventory.py before this test")
        cls.inventory = json.loads(cls.inventory_path.read_text(encoding="utf-8"))

    def test_inventory_protects_execution_boundary(self) -> None:
        policy = self.inventory["execution_policy"]
        for field in (
            "raw_iq_read",
            "matlab_started",
            "sage_started",
            "batch_started",
            "stage4_used",
            "formal_manuscript_modified",
            "v1_modified",
            "v2_modified",
            "evidence_matrix_modified",
            "handoff_modified",
        ):
            self.assertFalse(policy[field])

    def test_inventory_contains_all_read_only_sources_and_valid_hashes(self) -> None:
        self.assertEqual(self.inventory["source_count"], 7)
        self.assertEqual(len(self.inventory["sources"]), 7)
        for source in self.inventory["sources"]:
            path = Path(source["path"])
            self.assertTrue(source["read_only"])
            self.assertTrue(path.is_file())
            self.assertEqual(source["size_bytes"], path.stat().st_size)
            self.assertEqual(source["sha256"], sha256_file(path))

    def test_sources_are_v2_inputs_and_output_is_v3(self) -> None:
        self.assertIn("review_v2_doppler_audit", self.inventory["sources"][0]["path"])
        self.assertIn("review_v3_conditional_gmm", self.inventory["output_root"])
        for source in self.inventory["sources"]:
            self.assertNotIn("review_v3_conditional_gmm", source["path"])


if __name__ == "__main__":
    unittest.main()
