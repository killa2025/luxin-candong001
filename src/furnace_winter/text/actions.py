from __future__ import annotations

from typing import Any

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import TextEntry, TextRegistry, TextVisibility


_PATCH034_SOURCE = (
    "docs/handoff/PATCH-034：高频操作提示文案收口实现记录.md"
)

_RUNTIME_TEXT = {
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


def build_action_text_registry() -> TextRegistry:
    """Register Patch 034 confirmed operation and requirement text."""

    registry = TextRegistry()
    for text_id, text in _RUNTIME_TEXT.items():
        registry.register(
            TextEntry(
                text_id=text_id,
                text=text,
                status=ConfigStatus.FINAL,
                visibility=TextVisibility.PLAYER_VISIBLE,
                source=_PATCH034_SOURCE,
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
