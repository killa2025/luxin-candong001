from __future__ import annotations

from dataclasses import dataclass

from furnace_winter.interface.commands import CommandSpec
from furnace_winter.models import GameState


PROTOCOL_VERSION = 1


@dataclass(frozen=True, slots=True)
class Observation:
    """Machine-readable state view; command schemas are capabilities, not advice."""

    protocol_version: int
    state: GameState
    available_commands: tuple[CommandSpec, ...] = ()

    @classmethod
    def from_state(
        cls,
        state: GameState,
        available_commands: tuple[CommandSpec, ...] = (),
    ) -> Observation:
        return cls(
            protocol_version=PROTOCOL_VERSION,
            state=state,
            available_commands=available_commands,
        )
