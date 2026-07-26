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
        index = (REPOSITORY_ROOT / "docs" / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("`docs/PENDING.md`", index)
        self.assertNotIn("handoff/PENDING 登记.md", index)

    def test_repository_status_text_matches_patch_007(self) -> None:
        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        agents = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("已完成代码 Patch 007", readme)
        self.assertIn("data/technologies.json", readme)
        self.assertIn("data/events.json", readme)
        self.assertNotIn("当前骨架阶段不包含游戏代码", agents)


if __name__ == "__main__":
    unittest.main()
