from __future__ import annotations

import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RepositoryDocumentationTests(unittest.TestCase):
    def test_pending_has_one_authoritative_navigation_file(self) -> None:
        self.assertTrue((REPOSITORY_ROOT / "docs" / "PENDING.md").is_file())
        self.assertFalse(
            (REPOSITORY_ROOT / "docs" / "handoff" / "PENDING 登记.md").exists()
        )
        index = (REPOSITORY_ROOT / "docs" / "INDEX.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`docs/PENDING.md`", index)
        self.assertNotIn("handoff/PENDING 登记.md", index)

    def test_repository_status_text_matches_patch_026_boundary(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Patch 009", readme)
        self.assertIn("data/technologies.json", readme)
        self.assertIn("data/events.json", readme)
        self.assertIn("data/oath_order.json", readme)
        self.assertIn("data/final_frost.json", readme)
        self.assertIn("data/maps.json", readme)
        self.assertIn("当前存档数据版本为 v17", readme)
        self.assertIn("PATCH-011", readme)
        self.assertIn("PATCH-012", readme)
        self.assertIn("Patch 013", readme)
        self.assertIn("Patch 019", readme)
        self.assertIn("Patch 020", readme)
        self.assertIn("Patch 021", readme)
        self.assertIn("Patch 022", readme)
        self.assertIn("Patch 024", readme)
        self.assertIn("Patch 025", readme)
        self.assertIn("Patch 026", readme)
        self.assertIn("GameSession", readme)
        self.assertIn("Patch 022", agents)
        self.assertIn("Patch 023", agents)
        self.assertIn("Patch 024", agents)
        self.assertIn("Patch 025", agents)
        self.assertIn("Patch 026", agents)
        self.assertIn("TEST_NUMERIC", agents)
        self.assertIn("legacy_patch021", agents)
        self.assertIn("patch022", agents)


if __name__ == "__main__":
    unittest.main()
