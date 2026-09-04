from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from furnace_winter.interface.commands import CommandSpec
from furnace_winter.models import GameState


PROTOCOL_VERSION = 1


@dataclass(frozen=True, slots=True)
class Observation:
    """Machine-readable state view; command schemas are capabilities, not advice."""

    protocol_version: int
    state: GameState
    available_commands: tuple[CommandSpec, ...] = ()
    unavailable_commands: tuple[CommandSpec, ...] = ()
    available_rule_sections: tuple[str, ...] = ()
    protocol_contract: dict[str, Any] | None = None
    event_views: tuple[dict[str, Any], ...] = ()
    promise_views: tuple[dict[str, Any], ...] = ()
    map_view: dict[str, Any] | None = None
    law_view: dict[str, Any] | None = None
    technology_view: tuple[dict[str, Any], ...] = ()
    old_city_view: dict[str, Any] | None = None
    oath_order_view: dict[str, Any] | None = None
    final_frost_view: dict[str, Any] | None = None
    ending_report_view: dict[str, Any] | None = None
    heat_view: dict[str, Any] | None = field(default=None, kw_only=True)

    @classmethod
    def from_state(
        cls,
        state: GameState,
        available_commands: tuple[CommandSpec, ...] = (),
        *,
        available_rule_sections: tuple[str, ...] = (),
        protocol_contract: dict[str, Any] | None = None,
        event_views: tuple[dict[str, Any], ...] = (),
        promise_views: tuple[dict[str, Any], ...] = (),
        map_view: dict[str, Any] | None = None,
        law_view: dict[str, Any] | None = None,
        technology_view: tuple[dict[str, Any], ...] = (),
        old_city_view: dict[str, Any] | None = None,
        oath_order_view: dict[str, Any] | None = None,
        final_frost_view: dict[str, Any] | None = None,
        ending_report_view: dict[str, Any] | None = None,
        heat_view: dict[str, Any] | None = None,
    ) -> Observation:
        return cls(
            protocol_version=PROTOCOL_VERSION,
            state=state,
            available_commands=tuple(
                spec for spec in available_commands if spec.executable
            ),
            unavailable_commands=tuple(
                spec for spec in available_commands if not spec.executable
            ),
            available_rule_sections=available_rule_sections,
            protocol_contract=protocol_contract,
            event_views=event_views,
            promise_views=promise_views,
            map_view=map_view,
            law_view=law_view,
            technology_view=technology_view,
            old_city_view=old_city_view,
            oath_order_view=oath_order_view,
            final_frost_view=final_frost_view,
            ending_report_view=ending_report_view,
            heat_view=heat_view,
        )
