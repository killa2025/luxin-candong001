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

    def test_pending_uses_patch038_research_confirmation_contract(self) -> None:
        pending = (REPOSITORY_ROOT / "docs" / "PENDING.md").read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "`game.research` 继续无需 `confirm`",
            pending,
        )

    def test_patch039_deferred_research_contract_is_the_only_current_navigation(self) -> None:
        pending = (REPOSITORY_ROOT / "docs" / "PENDING.md").read_text(
            encoding="utf-8"
        )
        index = (REPOSITORY_ROOT / "docs" / "INDEX.md").read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "科技可研究并保留 `DEFERRED` 元数据",
            pending,
        )
        self.assertIn(
            "唯一可研究的 `DEFERRED` 结构前置",
            pending,
        )
        self.assertIn(
            "普通 `DEFERRED` 科技不得新开研究",
            pending,
        )
        self.assertIn(
            "PATCH-039：科技说明与延后研究门禁实现记录",
            index,
        )
        self.assertIn(
            "PATCH-038：开始研究确认与投入反馈实现记录 | Patch 038 交付记录 | 当前施工记录 | 已完成复审、已合并 main、第三十五次黑盒验收通过",
            index,
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-039：科技说明与延后研究门禁实现记录.md"
            ).is_file()
        )
        self.assertIn(
            "Patch 034 的非确认口径已被 Patch 038 用户覆盖；"
            "当前 `game.research` 仅在 `confirm=true` 时执行",
            pending,
        )

    def test_patch040_triage_is_documented_as_existing_but_unavailable(self) -> None:
        pending = (REPOSITORY_ROOT / "docs" / "PENDING.md").read_text(
            encoding="utf-8"
        )
        index = (REPOSITORY_ROOT / "docs" / "INDEX.md").read_text(
            encoding="utf-8"
        )
        handoff = (
            REPOSITORY_ROOT
            / "docs"
            / "handoff"
            / "PATCH-040：分级救治执行暂停与能力可见性实现记录.md"
        ).read_text(encoding="utf-8")

        for field in (
            "`command_exists=true`",
            "`executable=false`",
            "`unavailable_reason=triage_rules_unsealed`",
        ):
            self.assertIn(field, pending)
        self.assertIn(
            "PATCH-040：分级救治执行暂停与能力可见性实现记录",
            index,
        )
        self.assertIn("以下 12 项必须全部获得正式口径", handoff)
        self.assertIn("不提升存档版本", handoff)
        self.assertNotIn("不得实现 Patch 040", handoff)

    def test_patch041_triage_law_pause_is_documented(self) -> None:
        pending = (REPOSITORY_ROOT / "docs" / "PENDING.md").read_text(
            encoding="utf-8"
        )
        index = (REPOSITORY_ROOT / "docs" / "INDEX.md").read_text(
            encoding="utf-8"
        )
        handoff = (
            REPOSITORY_ROOT
            / "docs"
            / "handoff"
            / "PATCH-041：炉律动作可执行性审计实现记录.md"
        ).read_text(encoding="utf-8")

        self.assertIn("`unavailable_laws`", pending)
        self.assertIn("`unavailable_actions`", pending)
        self.assertIn("PATCH-041：炉律动作可执行性审计实现记录", index)
        self.assertIn("共登记 27 个命令；26 个可执行", handoff)
        self.assertIn("不提升存档版本", handoff)
        self.assertNotIn("不得实现 Patch 041", handoff)

    def test_repository_status_text_matches_patch_033_boundary(self) -> None:
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
        self.assertIn("Patch 026", readme)
        self.assertIn("Patch 027", readme)
        self.assertIn("Patch 029", readme)
        self.assertIn("Patch 030", readme)
        self.assertIn("Patch 031", readme)
        self.assertIn("Patch 032", readme)
        self.assertIn("Patch 033", readme)
        self.assertIn("Patch 034", readme)
        self.assertIn("Patch 035", readme)
        self.assertIn("Patch 036", readme)
        self.assertIn("格式 5", readme)
        self.assertIn('{"type":"autosave"}', readme)
        self.assertIn("command_specs", readme)
        self.assertIn("GameSession", readme)
        self.assertIn("Patch 022", agents)
        self.assertIn("Patch 030", agents)
        self.assertIn("Patch 031", agents)
        self.assertIn("Patch 032", agents)
        self.assertIn("Patch 033", agents)
        self.assertIn("Patch 034", agents)
        self.assertIn("Patch 035", agents)
        self.assertIn("Patch 036", agents)
        self.assertIn("TEST_NUMERIC", agents)
        self.assertIn("legacy_patch021", agents)
        self.assertIn("patch022", agents)
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-029：终局缺失正文收口实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-031：事件缺失正文收口实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-032：旧城派阶段事件正文收口实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-033：事件与承诺反馈文案收口实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-034：高频操作提示文案收口实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-035：社会路线条件反馈文案接线实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-036：分级救治条件反馈文案接线实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-037：取消研究确认与损失反馈实现记录.md"
            ).is_file()
        )
        self.assertTrue(
            (
                REPOSITORY_ROOT
                / "docs"
                / "handoff"
                / "PATCH-030：终局路线与制度长文收口实现记录.md"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
