from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from furnace_winter.models.randomness import RandomState
from furnace_winter.models.serialization import to_primitive
from furnace_winter.models.state import (
    CURRENT_SAVE_DATA_VERSION,
    BuildingState,
    CalendarState,
    EventState,
    FinalResultState,
    FurnaceState,
    GameState,
    LawState,
    OldCityState,
    PopulationState,
    PromiseState,
    ResourceState,
    TechState,
)


class SaveDataError(ValueError):
    pass


Migration = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(slots=True)
class SaveMigrationRegistry:
    current_version: int = CURRENT_SAVE_DATA_VERSION
    _migrations: dict[int, Migration] = field(default_factory=dict, init=False)

    def register(self, from_version: int, migration: Migration) -> None:
        if from_version >= self.current_version:
            raise ValueError("migration source must be older than current version")
        if from_version in self._migrations:
            raise ValueError(f"migration already registered for version {from_version}")
        self._migrations[from_version] = migration

    def migrate(self, document: Mapping[str, Any]) -> dict[str, Any]:
        migrated = deepcopy(dict(document))
        version = migrated.get("save_data_version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise SaveDataError("save_data_version must be an integer")
        if version > self.current_version:
            raise SaveDataError(f"save version {version} is newer than supported version")

        while version < self.current_version:
            migration = self._migrations.get(version)
            if migration is None:
                raise SaveDataError(f"no migration registered for save version {version}")
            migrated = migration(migrated)
            next_version = migrated.get("save_data_version")
            if next_version != version + 1:
                raise SaveDataError("migration must advance save_data_version by exactly one")
            version = next_version
        return migrated


def encode_game_state(state: GameState) -> dict[str, Any]:
    return to_primitive(state)


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SaveDataError(f"{field_name} must be an object")
    return dict(value)


def decode_game_state(
    document: Mapping[str, Any],
    migrations: SaveMigrationRegistry | None = None,
) -> GameState:
    data = (migrations or SaveMigrationRegistry()).migrate(document)
    try:
        random_data = _mapping(data["random"], "random")
        building_data = _mapping(data.get("buildings", {}), "buildings")
        buildings = {
            building_id: BuildingState(**_mapping(value, f"buildings.{building_id}"))
            for building_id, value in building_data.items()
        }
        return GameState(
            save_data_version=data["save_data_version"],
            random=RandomState(**random_data),
            command_sequence=data.get("command_sequence", 0),
            calendar=CalendarState(**_mapping(data.get("calendar", {}), "calendar")),
            population=PopulationState(**_mapping(data.get("population", {}), "population")),
            resources=ResourceState(**_mapping(data.get("resources", {}), "resources")),
            furnace=FurnaceState(**_mapping(data.get("furnace", {}), "furnace")),
            buildings=buildings,
            laws=LawState(**_mapping(data.get("laws", {}), "laws")),
            technologies=TechState(
                **_mapping(data.get("technologies", {}), "technologies")
            ),
            events=EventState(**_mapping(data.get("events", {}), "events")),
            promises=PromiseState(**_mapping(data.get("promises", {}), "promises")),
            old_city=OldCityState(**_mapping(data.get("old_city", {}), "old_city")),
            final_result=FinalResultState(
                **_mapping(data.get("final_result", {}), "final_result")
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, SaveDataError):
            raise
        raise SaveDataError(f"invalid save data: {exc}") from exc
