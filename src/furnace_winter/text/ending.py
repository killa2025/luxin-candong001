from __future__ import annotations

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import (
    PendingEntry,
    PendingRegistry,
    TextEntry,
    TextRegistry,
    TextVisibility,
)


_SOURCE = (
    "docs/text-assets/第 6 轮：FrostFinal  Ending  HardFail  "
    "EndingReport  EndingTag  Interrogation.md"
)

_RUNTIME_TEXT = {
    "ending.title.hard_fail": "炉城终止",
    "ending.title.high_victory": "炉城存续",
    "ending.title.standard_victory": "炉城越冬",
    "ending.title.bitter_victory": "炉城残胜",
    "ending.title.collapse_survival": "崩坏幸存",
    "ending.title.ember_survival": "残火未灭",
    "ending.title.player_ended": "执政官终止执政",
    "ending.hard_fail.population_zero.reason": (
        "炉城最后一次点名时，没有人回答。"
    ),
    "ending.hard_fail.core_collapse.reason": (
        "炉心越过红线后，再也没有回到执政官的命令里。"
    ),
    "ending.hard_fail.trust_exile.reason": (
        "居民不再相信你有资格继续带领他们。"
    ),
    "ending.hard_fail.panic_expelled.reason": (
        "居民害怕你，胜过害怕门外的风雪。"
    ),
    "ending.player_ended.status": "本局由执政官亲手封存。",
    "ending.player_ended.closing": (
        "炉城档案封存。\n\n"
        "不是因为所有问题都有了答案。\n"
        "而是因为执政官决定，不再继续追问。"
    ),
}

_PENDING_SELECTION_IDS = (
    "ending.high_victory.body_pool",
    "ending.standard_victory.body_pool",
    "ending.bitter_victory.body_pool",
    "ending.collapse_survival.body_pool",
    "ending.ember_survival.body_pool",
    "ending.player_ended.body_pool",
    "ending.hard_fail.population_zero.body_pool",
    "ending.hard_fail.core_collapse.body_pool",
    "ending.hard_fail.trust_exile.body_pool",
    "ending.hard_fail.panic_expelled.body_pool",
    "ending.hard_fail.closing_pool",
    "ending.report.illness.pool",
    "ending.report.trust_panic.pool",
    "ending.report.core.pool",
    "ending.report.coal_food.pool",
    "ending.report.future.pool",
    "ending.additional.death.pool",
    "ending.additional.medical.pool",
    "ending.additional.food.pool",
    "ending.additional.core.pool",
    "ending.additional.society.pool",
    "ending.additional.housing.pool",
    "ending.interrogation.general.pool",
    "ending.interrogation.high_victory.pool",
    "ending.interrogation.cost.pool",
    "ending.interrogation.ember.pool",
    "ending.interrogation.hard_fail.pool",
)


def build_ending_text_registry() -> TextRegistry:
    """Register only complete, non-pool Patch 010 runtime text."""

    registry = TextRegistry()
    for text_id, text in _RUNTIME_TEXT.items():
        registry.register(
            TextEntry(
                text_id=text_id,
                text=text,
                status=ConfigStatus.FINAL,
                visibility=TextVisibility.PLAYER_VISIBLE,
                source=_SOURCE,
            )
        )
    return registry


def build_ending_pending_registry() -> PendingRegistry:
    """Track text or selection metadata that Patch 010 must not invent."""

    registry = PendingRegistry()
    registry.register(
        PendingEntry(
            entry_id="ending.report.death_record_sentence",
            status=ConfigStatus.TODO_TEXT,
            source=_SOURCE,
            note="死亡处理对应的正式报告句尚未封存。",
        )
    )
    registry.register(
        PendingEntry(
            entry_id="ending.report.frostfall_deaths.zero_sentence",
            status=ConfigStatus.PENDING,
            source=_SOURCE,
            note="霜落死亡为零时的正式报告句尚未封存，本轮隐藏。",
        )
    )
    for entry_id in _PENDING_SELECTION_IDS:
        registry.register(
            PendingEntry(
                entry_id=entry_id,
                status=ConfigStatus.PENDING,
                source=_SOURCE,
                note="候选段落条件元数据未完整封存，不自动选择。",
            )
        )
    return registry
