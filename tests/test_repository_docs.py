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

    def test_repository_status_text_matches_patch_018_boundary(self) -> None:
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
        self.assertIn("Patch 017", readme)
        self.assertIn("Patch 018", readme)
        self.assertIn("暂行测试口径", readme)
        self.assertIn("不代表最终封存平衡值", readme)
        self.assertIn("铁腕路线", readme)
        self.assertIn("GameSession", readme)
        self.assertIn("Patch 018", agents)
        self.assertIn(
            "不得将这些值标成最终封存值",
            agents,
        )
        self.assertIn(
            "不得借此修改铁腕路线、医疗配给、第二研究所、住房、资源产出、科技成本、终霜强度或其他平衡数值",
            agents,
        )
        self.assertNotIn("完整结局报告正文、审问与 UI 仍留给 Patch 010", agents)


if __name__ == "__main__":
    unittest.main()
