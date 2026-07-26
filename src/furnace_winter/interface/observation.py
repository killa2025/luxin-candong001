from __future__ import annotations

from dataclasses import dataclass
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
    event_views: tuple[dict[str, Any], ...] = ()
    promise_views: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_state(
        cls,
        state: GameState,
        available_commands: tuple[CommandSpec, ...] = (),
        *,
        event_views: tuple[dict[str, Any], ...] = (),
        promise_views: tuple[dict[str, Any], ...] = (),
    ) -> Observation:
        return cls(
            protocol_version=PROTOCOL_VERSION,
            state=state,
            available_commands=available_commands,
            event_views=event_views,
            promise_views=promise_views,
        )
