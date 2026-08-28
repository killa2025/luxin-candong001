from __future__ import annotations

from furnace_winter.config import ConfigStatus
from furnace_winter.text.events import build_event_text_registry
from furnace_winter.text.registry import TextEntry, TextRegistry, TextVisibility


_SOURCE = "docs/handoff/PATCH-035：社会路线条件反馈文案接线实现记录.md"

_ROUTE_RUNTIME_TEXT = {
    "confirm.route.warning_mutual_exclusive": (
        "选择誓言路线后，铁腕路线及巡查所不会启用；"
        "选择铁腕路线后，誓言路线及守炉堂不会启用。"
    ),
    "requirement.oath_hall.enabled_running": (
        "守炉堂必须已启用，并处于运行状态。"
    ),
    "requirement.patrol_office.enabled_running": (
        "巡查所必须已启用，并处于运行状态。"
    ),
    "cooldown.route.not_ready.feedback": "誓言与铁腕炉约仍在冷却中。",
    "cooldown.route.next_available_day": (
        "下一条炉律可在第 {next_available_day} 天签署。"
    ),
    "requirement.old_city.active": "旧城派危机已激活时可用。",
    "requirement.cooked_food.enough": "需要拥有足够熟食。",
    "requirement.death_recent": "仅在近期存在死亡事件时可用。",
}


def build_oath_order_text_registry() -> TextRegistry:
    """Return event text plus the Patch 035 route feedback text."""

    registry = build_event_text_registry()
    for text_id, text in _ROUTE_RUNTIME_TEXT.items():
        registry.register(
            TextEntry(
                text_id=text_id,
                text=text,
                status=ConfigStatus.USER_OVERRIDE,
                visibility=TextVisibility.PLAYER_VISIBLE,
                source=_SOURCE,
            )
        )
    return registry


def render_route_text(
    registry: TextRegistry,
    text_id: str,
    **parameters: object,
) -> str:
    entry = registry.require(text_id)
    try:
        return entry.text.format(**parameters)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"route text parameters do not match {text_id}") from exc
