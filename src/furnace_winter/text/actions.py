from __future__ import annotations

from typing import Any

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import TextEntry, TextRegistry, TextVisibility


_PATCH034_SOURCE = (
    "docs/handoff/PATCH-034：高频操作提示文案收口实现记录.md"
)
_PATCH036_SOURCE = (
    "docs/handoff/PATCH-036：分级救治条件反馈文案接线实现记录.md"
)
_PATCH037_SOURCE = (
    "docs/handoff/PATCH-037：取消研究确认与损失反馈实现记录.md"
)
_PATCH038_SOURCE = (
    "docs/handoff/PATCH-038：开始研究确认与投入反馈实现记录.md"
)

_PATCH034_RUNTIME_TEXT = {
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
    "research.resource.not_enough": (
        "当前资源不足，无法开始这项研究。还缺少：{missing_resources}。"
    ),
}

_PATCH036_RUNTIME_TEXT = {
    "medical.triage.target_rule": "启动时必须指定一座医疗站或医院。",
    "medical.triage.care_home_forbidden": "不能指定养护所。",
}

_PATCH037_RUNTIME_TEXT = {
    "research.cancel.confirm": (
        "确认取消正在进行的「{technology_name}」研究？"
        "已经投入的木材与钢材不会返还，当前研究进度也会清零。"
    ),
}

_PATCH038_RUNTIME_TEXT = {
    "research.confirm.body": (
        "确认开始研究「{technology_name}」？本次研究将立即投入 {wood_cost} 木材与 "
        "{steel_cost} 钢材。研究完成前，这些资源不会返还；若中途取消，"
        "已经投入的资源与研究进度都将损失。"
    ),
}


def build_action_text_registry() -> TextRegistry:
    """Register confirmed operation and requirement text."""

    registry = TextRegistry()
    for source, status, entries in (
        (_PATCH034_SOURCE, ConfigStatus.FINAL, _PATCH034_RUNTIME_TEXT),
        (_PATCH036_SOURCE, ConfigStatus.FINAL, _PATCH036_RUNTIME_TEXT),
        (
            _PATCH037_SOURCE,
            ConfigStatus.USER_OVERRIDE,
            _PATCH037_RUNTIME_TEXT,
        ),
        (
            _PATCH038_SOURCE,
            ConfigStatus.USER_OVERRIDE,
            _PATCH038_RUNTIME_TEXT,
        ),
    ):
        for text_id, text in entries.items():
            registry.register(
                TextEntry(
                    text_id=text_id,
                    text=text,
                    status=status,
                    visibility=TextVisibility.PLAYER_VISIBLE,
                    source=source,
                )
            )
    return registry


def render_action_text(
    registry: TextRegistry,
    text_id: str,
    **values: Any,
) -> str:
    """Render one registered, trusted template with explicit runtime facts."""

    return registry.require(text_id).text.format(**values)
