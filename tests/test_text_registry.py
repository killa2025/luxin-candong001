from __future__ import annotations

import unittest

from furnace_winter.config import ConfigStatus
from furnace_winter.text import (
    DeprecatedEntry,
    DeprecatedRegistry,
    MissingTextError,
    PendingEntry,
    PendingRegistry,
    TextEntry,
    TextRegistry,
    TextRegistryError,
    TextVisibility,
    build_action_text_registry,
    build_event_text_registry,
)


def confirmed_entry(text_id: str = "test.confirmed") -> TextEntry:
    return TextEntry(
        text_id=text_id,
        text="测试文本",
        status=ConfigStatus.FINAL,
        visibility=TextVisibility.PLAYER_VISIBLE,
        source="tests",
    )


class TextRegistryTests(unittest.TestCase):
    def test_patch034_action_text_is_exact_and_final(self) -> None:
        registry = build_action_text_registry()
        expected = {
            "confirm.action.overtime_day.body": (
                "确认让「{building_name}」执行加班日？本日不可取消；普通生产提高至两倍，"
                "医疗与研究进度提高至 1.5 倍，但信任 -2、恐慌 +3，并会新增患病者与事故风险。"
            ),
            "confirm.action.emergency_ration.body": (
                "确认启用应急口粮？本日人均食物消耗降至一半，信任 -3、恐慌 +4；"
                "只持续当天，随后恢复此前配给，四天内不能再次使用。"
            ),
            "building.hospital.missing_requirement_hint": (
                "医院尚未解锁。需要先签署「基础医疗法」，并完成「医院标准化」研究。"
            ),
            "building.greenhouse.upgrade_missing_requirement_hint": (
                "温室还不能升级。需要先完成「温室改良」研究。"
            ),
            "building.house.upgrade_missing_requirement_hint": (
                "这座住宅还不能升级。需要先完成「{required_tech_name}」研究。"
            ),
            "research.confirm.body": (
                "开始研究「{technology_name}」时，木材 {wood_cost}、钢材 {steel_cost} 将立即扣除；"
                "同一时间不能进行其他研究。"
            ),
            "research.resource.not_enough": (
                "当前资源不足，无法开始这项研究。还缺少：{missing_resources}。"
            ),
        }

        self.assertEqual(
            {entry.text_id: entry.text for entry in registry.entries()},
            expected,
        )
        for entry in registry.entries():
            self.assertEqual(entry.status, ConfigStatus.FINAL)
            self.assertEqual(entry.visibility, TextVisibility.PLAYER_VISIBLE)
            self.assertIn("PATCH-034", entry.source)

    def test_event_text_is_registered_from_sealed_assets(self) -> None:
        registry = build_event_text_registry()

        self.assertEqual(
            registry.require("event.black_frost_echo.title").text,
            "黑霜回声",
        )
        self.assertEqual(
            registry.require("event.final_preparation_window.option_c").text,
            "压下恐慌，继续日常运转",
        )
        self.assertEqual(
            registry.require("event.city_night_terror.option_c").text,
            "不再粉饰情况",
        )
        self.assertIn(
            "我们今天要去哪儿",
            registry.require("event.children_request.body").text,
        )
        self.assertEqual(
            registry.require("arrival.day37.title").text,
            "后期难民潮",
        )
        self.assertEqual(
            registry.require("arrival.option.accept_partial").text,
            "部分接纳",
        )
        self.assertEqual(
            registry.require("event.seventh_frost_start.title").text,
            "第七霜落",
        )

    def test_all_sealed_runtime_event_panels_are_registered(self) -> None:
        registry = build_event_text_registry()
        complete_events = (
            "empty_pot",
            "raw_food_dispute",
            "medical_beds_emergency",
            "severe_case_backlog",
            "first_body",
            "bodies_under_snow",
            "children_request",
            "red_frozen_hands",
            "long_shift_collapse",
            "overtime_empty_post",
            "coal_bottom",
            "cold_house_night",
            "trust_crack",
            "city_unrest",
        )
        for event_id in complete_events:
            with self.subTest(event_id=event_id):
                for suffix in ("title", "body", "option_a", "option_b", "option_c"):
                    self.assertIsNotNone(
                        registry.get(f"event.{event_id}.{suffix}")
                    )
        for suffix in ("title", "warning", "option_a", "option_b", "option_c"):
            self.assertIsNotNone(registry.get(f"event.furnace_redline.{suffix}"))

    def test_patch031_user_override_event_bodies_are_exact_and_final(self) -> None:
        registry = build_event_text_registry()
        expected = {
            "event.long_shift_collapse.body": (
                "长班还没有结束，就有人在岗位旁倒了下去。\n"
                "没有事故，也没有巨响。只是身体终于比命令更早承认，它已经撑不住了。\n"
                "其他人停了一会儿，又重新回到工作里。\n"
                "炉城缺的从来不只是一双手。\n"
                "更缺的是允许那双手停下来的余地。"
            ),
            "event.overtime_empty_post.body": (
                "加班已经不是第一次。\n"
                "今天点名时，一个岗位没有等到应该站在那里的人。\n"
                "炉城仍然可以把别人调过去，把缺口重新填满。\n"
                "可岗位可以补，人却不能像名册上的数字一样无限往前挪。\n"
                "当每一个空位都需要另一个更疲惫的人顶上去时——\n"
                "迟早还会再空一个。"
            ),
            "arrival.day6.body": (
                "雪线外出现了一批求生者。\n"
                "他们没有带来足以改变炉城命运的东西，只带来了还能劳动的身体，以及身后已经无法回去的路。\n"
                "城里的人看着他们。\n"
                "多几双手，也意味着多几张嘴。\n"
                "寒冬第一次逼你承认：\n"
                "救下一个人和养活一个人，从来不是同一道题。"
            ),
            "arrival.day19.body": (
                "一支残余工程队抵达了炉城。\n"
                "他们知道怎样修东西，也知道一座设施在彻底坏掉以前，会先发出什么声音。\n"
                "这本该算是好消息。\n"
                "可炉城现在最不缺的，正是需要修补的东西。\n"
                "新的工程人手走进城门时，没有人问他们还能建造什么。\n"
                "人们先问的是——\n"
                "还有什么来得及不让它坏掉。"
            ),
            "arrival.day37.body": (
                "黑霜之后，又有人出现在城外。\n"
                "这一次不是零散的求生者。\n"
                "越来越多的人挤在炉城能够看见的地方，等待一扇门决定他们接下来还能不能活。\n"
                "城里的食物、床位和燃料不会因为同情而变多。\n"
                "可把门关上以后，\n"
                "风雪也不会替你忘记门外还有人。"
            ),
            "event.seventh_frost_start.body": (
                "第七霜落来了。\n"
                "从今天起，城外不再是可以指望的退路，炉心、食物、医疗和住房都会被压到最后的余量。\n"
                "之前所有被拖延的问题，现在都要一起结账。\n"
                "炉城已经没有多少东西可以再失去。\n"
                "接下来的七天，只会回答一个问题：\n"
                "你此前选择保住的一切，\n"
                "究竟够不够撑到风停。"
            ),
        }

        for text_id, text in expected.items():
            with self.subTest(text_id=text_id):
                entry = registry.require(text_id)
                self.assertEqual(entry.text, text)
                self.assertEqual(entry.status, ConfigStatus.FINAL)
                self.assertEqual(
                    entry.source,
                    "docs/handoff/PATCH-031：事件缺失正文收口实现记录.md",
                )

    def test_patch032_old_city_bodies_are_exact_and_final(self) -> None:
        registry = build_event_text_registry()
        expected = {
            "old_city.event.southern_letter.body": (
                "今天，一封从南方辗转送来的信进了炉城。\n"
                "信里的消息并不完整，却提到更远的地方或许仍有人活着，也许还有能够落脚的去处。\n"
                "没人知道这封信经过了多久，也没人能确认里面的话还剩几分真实。\n"
                "可只要“城外也许还有路”这句话被人看见，\n"
                "炉城就已经不再是唯一的答案。"
            ),
            "old_city.event.hidden_rumors.body": (
                "最近，关于离开炉城的消息开始在私下流传。\n"
                "有人说南边还有聚居地，有人说旧路并没有完全断掉，也有人只是反复问同一句话：\n"
                "这里真的是最后一个还能活下去的地方吗？\n"
                "这些话还没有被公开喊出来。\n"
                "它们只是出现在排队、换班和熄灯以后，\n"
                "越来越多人听见，也越来越少人愿意承认自己听见过。"
            ),
            "old_city.event.public_gathering.body": (
                "原本藏在低声交谈里的怀疑，今天第一次聚到了明面上。\n"
                "越来越多人停在公共区域，没有散去。\n"
                "他们谈论城外的去处，谈论炉城还能撑多久，也要求得到一个足以让人继续留下的答案。\n"
                "这还不是一场出走。\n"
                "但已经不再只是传言。\n"
                "当怀疑开始站在人群中央，\n"
                "执政官就不能再假装它只存在于角落里。"
            ),
            "old_city.event.exodus_countdown.body": (
                "旧城派的人数还在上升。\n"
                "如今，已经有人开始整理能够带走的东西，询问城门、路线和外面的天气。\n"
                "他们还没有真正离开。\n"
                "可“要不要走”正在变成“什么时候走”。\n"
                "炉城仍有时间。\n"
                "只是已经没人能再把这件事当成一句随时会散掉的抱怨。\n"
                "当有人开始为离开做准备时，\n"
                "留下本身，也开始需要一个理由。"
            ),
        }

        for text_id, text in expected.items():
            with self.subTest(text_id=text_id):
                entry = registry.require(text_id)
                self.assertEqual(entry.text, text)
                self.assertEqual(entry.status, ConfigStatus.FINAL)
                self.assertEqual(
                    entry.source,
                    "docs/handoff/PATCH-032：旧城派阶段事件正文收口实现记录.md",
                )

        sealed = {
            "old_city.event.southern_letter.title": "南方来信",
            "old_city.event.southern_letter.option_a": "公布来信",
            "old_city.event.southern_letter.option_b": "压下来信",
            "old_city.event.hidden_rumors.title": "暗中传言",
            "old_city.event.hidden_rumors.option_a": "公开解释",
            "old_city.event.hidden_rumors.option_b": "暂不处理",
            "old_city.event.public_gathering.title": "公开集结",
            "old_city.event.public_gathering.option_a": "公开说明",
            "old_city.event.public_gathering.option_b": "加强巡查",
            "old_city.event.public_gathering.option_c": "暂不处理",
            "old_city.event.exodus_countdown.title": "离城倒计时",
            "old_city.event.exodus_countdown.option_a": "承诺压低旧城派人数",
            "old_city.event.exodus_countdown.option_b": "暂不阻拦",
            "old_city.event.exodus_countdown.option_c": "争取最后时间",
        }
        for text_id, text in sealed.items():
            with self.subTest(text_id=text_id):
                entry = registry.require(text_id)
                self.assertEqual(entry.text, text)
                self.assertEqual(entry.status, ConfigStatus.FINAL)
                self.assertEqual(
                    entry.source,
                    "docs/text-assets/第 5 轮：Event  Promise  OldCity  FixedArrival  FrostWarning  Achievement.md",
                )

    def test_patch033_event_and_promise_feedback_is_exact_and_final(self) -> None:
        registry = build_event_text_registry()
        expected = {
            "event.option.unavailable.feedback": (
                "这个选项当前不可用。请查看返回的具体原因与所需条件。"
            ),
            "promise.same_type.active": (
                "同类型承诺仍在履行中。在它完成或失败以前，不能再次作出相同承诺。"
            ),
            "promise.success.title": "承诺兑现",
            "promise.failure.title": "承诺落空",
        }

        for text_id, text in expected.items():
            with self.subTest(text_id=text_id):
                entry = registry.require(text_id)
                self.assertEqual(entry.text, text)
                self.assertEqual(entry.status, ConfigStatus.FINAL)
                self.assertEqual(
                    entry.source,
                    "docs/handoff/PATCH-033：事件与承诺反馈文案收口实现记录.md",
                )

    def test_confirmed_text_can_be_looked_up(self) -> None:
        registry = TextRegistry()
        entry = confirmed_entry()
        registry.register(entry)

        self.assertEqual(registry.require(entry.text_id), entry)

    def test_missing_text_is_reported_and_raises_on_require(self) -> None:
        registry = TextRegistry()
        registry.register(confirmed_entry())

        report = registry.report_missing(["test.confirmed", "test.missing"])

        self.assertFalse(report.is_complete)
        self.assertEqual(report.missing_ids, ("test.missing",))
        with self.assertRaises(MissingTextError):
            registry.require("test.missing")

    def test_pending_todo_and_deprecated_are_isolated(self) -> None:
        pending = PendingRegistry()
        pending.register(
            PendingEntry("text.pending", ConfigStatus.PENDING, source="tests")
        )
        pending.register(
            PendingEntry("text.todo", ConfigStatus.TODO_TEXT, source="tests")
        )
        deprecated = DeprecatedRegistry()
        deprecated.register(DeprecatedEntry("text.old", source="tests"))

        runtime = TextRegistry()

        self.assertEqual(pending.todo_text_ids(), ("text.todo",))
        self.assertTrue(deprecated.contains("text.old"))
        self.assertEqual(runtime.entries(), ())

    def test_non_runtime_and_internal_text_are_rejected(self) -> None:
        registry = TextRegistry()
        with self.assertRaises(TextRegistryError):
            registry.register(
                TextEntry(
                    "text.todo",
                    "未完成",
                    ConfigStatus.TODO_TEXT,
                    TextVisibility.PLAYER_VISIBLE,
                    "tests",
                )
            )
        with self.assertRaises(TextRegistryError):
            registry.register(
                TextEntry(
                    "text.internal",
                    "内部",
                    ConfigStatus.FINAL,
                    TextVisibility.SYSTEM_INTERNAL,
                    "tests",
                )
            )

    def test_blank_text_and_non_normalized_text_ids_are_rejected(self) -> None:
        registry = TextRegistry()
        for entry in (
            TextEntry(
                "text.blank",
                "   ",
                ConfigStatus.FINAL,
                TextVisibility.PLAYER_VISIBLE,
                "tests",
            ),
            confirmed_entry(""),
            confirmed_entry("   "),
            confirmed_entry(" text.spaced"),
            confirmed_entry("text.spaced "),
        ):
            with self.subTest(entry=entry), self.assertRaises(TextRegistryError):
                registry.register(entry)

    def test_pending_and_deprecated_ids_must_be_normalized(self) -> None:
        for entry_id in ("", "   ", " pending.id", "deprecated.id "):
            with self.subTest(entry_id=entry_id):
                with self.assertRaises(ValueError):
                    PendingRegistry().register(
                        PendingEntry(entry_id, ConfigStatus.PENDING, source="tests")
                    )
                with self.assertRaises(ValueError):
                    DeprecatedRegistry().register(
                        DeprecatedEntry(entry_id, source="tests")
                    )
if __name__ == "__main__":
    unittest.main()
