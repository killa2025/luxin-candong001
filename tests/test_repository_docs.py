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

    def test_repository_status_text_matches_patch_020_boundary(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Patch 009", readme)
        self.assertIn("data/technologies.json", readme)
        self.assertIn("data/events.json", readme)
        self.assertIn("data/oath_order.json", readme)
        self.assertIn("data/final_frost.json", readme)
        self.assertIn("data/maps.json", readme)
        self.assertIn("当前存档数据版本为 v14", readme)
        self.assertIn("PATCH-011", readme)
        self.assertIn("PATCH-012", readme)
        self.assertIn("Patch 013", readme)
        self.assertIn("Patch 019", readme)
        self.assertIn("Patch 020", readme)
        self.assertIn("终局主文案", readme)
        self.assertIn("不会重抽", readme)
        self.assertIn("GameSession", readme)
        self.assertIn("Patch 020", agents)
        self.assertIn(
            "不得添加“本局共有”",
            agents,
        )
        self.assertIn(
            "009-C 完整路线长文、正式随机权重、无法证明的器官/灰烬叙述",
            agents,
        )
        self.assertIn("平衡数值", agents)


if __name__ == "__main__":
    unittest.main()
