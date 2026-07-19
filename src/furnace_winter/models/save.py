from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields
from typing import Any

from furnace_winter.models.randomness import RANDOM_ALGORITHM, RandomState
from furnace_winter.models.serialization import to_primitive
from furnace_winter.models.state import (
    CURRENT_SAVE_DATA_VERSION,
    FINAL_DAY,
    BuildingState,
    CalendarState,
    EventState,
    FinalResultState,
    FurnaceState,
    GameState,
    HardFailType,
    LawState,
    OldCityState,
    PopulationState,
    PromiseState,
    ResourceState,
    TechState,
    TrustPanicState,
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
        if not isinstance(document, Mapping):
            raise SaveDataError("save data must be an object")
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
            migrated_value = migration(migrated)
            if not isinstance(migrated_value, Mapping):
                raise SaveDataError("migration must return an object")
            migrated = dict(migrated_value)
            next_version = migrated.get("save_data_version")
            if next_version != version + 1:
                raise SaveDataError(
                    "migration must advance save_data_version by exactly one"
                )
            version = next_version
        return migrated


def encode_game_state(state: GameState) -> dict[str, Any]:
    return to_primitive(state)


def _field_names(model: type[Any]) -> tuple[str, ...]:
    return tuple(item.name for item in fields(model))


def _object(value: Any, path: str, required: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SaveDataError(f"{path} must be an object")
    data = dict(value)
    missing = sorted(set(required) - set(data))
    unknown = sorted(set(data) - set(required))
    if missing:
        raise SaveDataError(f"{path} is missing required fields: {missing}")
    if unknown:
        raise SaveDataError(f"{path} contains unknown fields: {unknown}")
    return data


def _integer(
    value: Any,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SaveDataError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise SaveDataError(f"{path} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise SaveDataError(f"{path} must be at most {maximum}")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise SaveDataError(f"{path} must be a boolean")
    return value


def _string(value: Any, path: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        suffix = " or null" if optional else ""
        raise SaveDataError(f"{path} must be a normalized non-empty string{suffix}")
    return value


def _string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise SaveDataError(f"{path} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        checked = _string(item, f"{path}[{index}]")
        assert isinstance(checked, str)
        result.append(checked)
    return result


def _nonnegative_int_object(value: Any, path: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise SaveDataError(f"{path} must be an object")
    result: dict[str, int] = {}
    for key, item in value.items():
        checked_key = _string(key, f"{path} key")
        assert isinstance(checked_key, str)
        result[checked_key] = _integer(item, f"{path}.{checked_key}", minimum=0)
    return result


def _decode_random(value: Any) -> RandomState:
    data = _object(value, "random", _field_names(RandomState))
    state = RandomState(
        seed=_integer(data["seed"], "random.seed"),
        internal_state=_integer(data["internal_state"], "random.internal_state"),
        draws=_integer(data["draws"], "random.draws", minimum=0),
        algorithm=_string(data["algorithm"], "random.algorithm"),
    )
    if state.algorithm != RANDOM_ALGORITHM:
        raise SaveDataError(f"unsupported random algorithm: {state.algorithm}")
    return state


def _decode_calendar(value: Any) -> CalendarState:
    data = _object(value, "calendar", _field_names(CalendarState))
    current_day = _integer(data["current_day"], "calendar.current_day", minimum=1)
    max_day = _integer(data["max_day"], "calendar.max_day", minimum=1)
    if max_day != FINAL_DAY:
        raise SaveDataError(f"calendar.max_day must equal {FINAL_DAY}")
    if current_day > max_day:
        raise SaveDataError("calendar.current_day must not exceed calendar.max_day")
    return CalendarState(
        current_day=current_day,
        max_day=max_day,
        current_phase=_string(
            data["current_phase"], "calendar.current_phase", optional=True
        ),
        is_day_locked=_boolean(data["is_day_locked"], "calendar.is_day_locked"),
        is_end_day_confirmed=_boolean(
            data["is_end_day_confirmed"], "calendar.is_end_day_confirmed"
        ),
    )


def _decode_nonnegative_int_state(
    value: Any,
    path: str,
    model: type[PopulationState] | type[ResourceState],
) -> PopulationState | ResourceState:
    names = _field_names(model)
    data = _object(value, path, names)
    values = {
        name: _integer(data[name], f"{path}.{name}", minimum=0) for name in names
    }
    return model(**values)


def _decode_trust_panic(value: Any) -> TrustPanicState:
    data = _object(value, "trust_panic", _field_names(TrustPanicState))
    values: dict[str, int | None] = {}
    for name in ("trust", "panic"):
        item = data[name]
        values[name] = (
            None
            if item is None
            else _integer(item, f"trust_panic.{name}", minimum=0, maximum=100)
        )
    return TrustPanicState(**values)


def _decode_furnace(value: Any) -> FurnaceState:
    data = _object(value, "furnace", _field_names(FurnaceState))
    return FurnaceState(
        is_active=_boolean(data["is_active"], "furnace.is_active"),
        mode_id=_string(data["mode_id"], "furnace.mode_id", optional=True),
        pressure=_integer(data["pressure"], "furnace.pressure", minimum=0),
    )


def _decode_building(value: Any, path: str, expected_id: str) -> BuildingState:
    data = _object(value, path, _field_names(BuildingState))
    building_id = _string(data["building_id"], f"{path}.building_id")
    if building_id != expected_id:
        raise SaveDataError(f"{path}.building_id must match its map key")
    return BuildingState(
        building_id=building_id,
        building_type=_string(data["building_type"], f"{path}.building_type"),
        zone=_string(data["zone"], f"{path}.zone"),
        slot_size=_integer(data["slot_size"], f"{path}.slot_size", minimum=0),
        is_built=_boolean(data["is_built"], f"{path}.is_built"),
        is_operational=_boolean(data["is_operational"], f"{path}.is_operational"),
        assigned_workers=_integer(
            data["assigned_workers"], f"{path}.assigned_workers", minimum=0
        ),
        assigned_engineers=_integer(
            data["assigned_engineers"], f"{path}.assigned_engineers", minimum=0
        ),
        assigned_children=_integer(
            data["assigned_children"], f"{path}.assigned_children", minimum=0
        ),
        assigned_medical_apprentices=_integer(
            data["assigned_medical_apprentices"],
            f"{path}.assigned_medical_apprentices",
            minimum=0,
        ),
        assigned_engineering_apprentices=_integer(
            data["assigned_engineering_apprentices"],
            f"{path}.assigned_engineering_apprentices",
            minimum=0,
        ),
        can_heat=_boolean(data["can_heat"], f"{path}.can_heat"),
        heated_today=_boolean(data["heated_today"], f"{path}.heated_today"),
        effective_temperature=_integer(
            data["effective_temperature"], f"{path}.effective_temperature"
        ),
        is_shutdown_by_temperature=_boolean(
            data["is_shutdown_by_temperature"],
            f"{path}.is_shutdown_by_temperature",
        ),
    )


def _decode_buildings(value: Any) -> dict[str, BuildingState]:
    if not isinstance(value, Mapping):
        raise SaveDataError("buildings must be an object")
    result: dict[str, BuildingState] = {}
    for key, item in value.items():
        building_id = _string(key, "buildings key")
        assert isinstance(building_id, str)
        result[building_id] = _decode_building(
            item, f"buildings.{building_id}", building_id
        )
    return result


def _decode_laws(value: Any) -> LawState:
    data = _object(value, "laws", _field_names(LawState))
    return LawState(
        signed_law_ids=_string_list(data["signed_law_ids"], "laws.signed_law_ids"),
        active_law_ids=_string_list(data["active_law_ids"], "laws.active_law_ids"),
        cooldowns=_nonnegative_int_object(data["cooldowns"], "laws.cooldowns"),
    )


def _decode_technologies(value: Any) -> TechState:
    data = _object(value, "technologies", _field_names(TechState))
    return TechState(
        researched_tech_ids=_string_list(
            data["researched_tech_ids"], "technologies.researched_tech_ids"
        ),
        active_research_id=_string(
            data["active_research_id"],
            "technologies.active_research_id",
            optional=True,
        ),
        research_progress_days=_integer(
            data["research_progress_days"],
            "technologies.research_progress_days",
            minimum=0,
        ),
    )


def _decode_events(value: Any) -> EventState:
    data = _object(value, "events", _field_names(EventState))
    return EventState(
        active_event_ids=_string_list(data["active_event_ids"], "events.active_event_ids"),
        resolved_event_ids=_string_list(
            data["resolved_event_ids"], "events.resolved_event_ids"
        ),
    )


def _decode_promises(value: Any) -> PromiseState:
    data = _object(value, "promises", _field_names(PromiseState))
    return PromiseState(
        active_promise_ids=_string_list(
            data["active_promise_ids"], "promises.active_promise_ids"
        ),
        completed_promise_ids=_string_list(
            data["completed_promise_ids"], "promises.completed_promise_ids"
        ),
        failed_promise_ids=_string_list(
            data["failed_promise_ids"], "promises.failed_promise_ids"
        ),
    )


def _decode_old_city(value: Any) -> OldCityState:
    data = _object(value, "old_city", _field_names(OldCityState))
    return OldCityState(
        is_unlocked=_boolean(data["is_unlocked"], "old_city.is_unlocked"),
        active_stage_id=_string(
            data["active_stage_id"], "old_city.active_stage_id", optional=True
        ),
    )


def _decode_final_result(value: Any) -> FinalResultState:
    data = _object(value, "final_result", _field_names(FinalResultState))
    hard_fail_value = _string(
        data["hard_fail_type"], "final_result.hard_fail_type", optional=True
    )
    try:
        hard_fail_type = (
            None if hard_fail_value is None else HardFailType(hard_fail_value)
        )
    except ValueError as exc:
        raise SaveDataError(
            f"unsupported hard_fail_type: {hard_fail_value}"
        ) from exc
    return FinalResultState(
        is_finalized=_boolean(data["is_finalized"], "final_result.is_finalized"),
        ending_id=_string(data["ending_id"], "final_result.ending_id", optional=True),
        hard_fail_type=hard_fail_type,
        ending_tags=_string_list(data["ending_tags"], "final_result.ending_tags"),
    )


def decode_game_state(
    document: Mapping[str, Any],
    migrations: SaveMigrationRegistry | None = None,
) -> GameState:
    data = (migrations or SaveMigrationRegistry()).migrate(document)
    data = _object(data, "$", _field_names(GameState))
    try:
        save_data_version = _integer(
            data["save_data_version"], "save_data_version", minimum=1
        )
        if save_data_version != CURRENT_SAVE_DATA_VERSION:
            raise SaveDataError(
                f"save version {save_data_version} does not match current schema"
            )
        return GameState(
            save_data_version=save_data_version,
            random=_decode_random(data["random"]),
            command_sequence=_integer(
                data["command_sequence"], "command_sequence", minimum=0
            ),
            calendar=_decode_calendar(data["calendar"]),
            population=_decode_nonnegative_int_state(
                data["population"], "population", PopulationState
            ),
            resources=_decode_nonnegative_int_state(
                data["resources"], "resources", ResourceState
            ),
            trust_panic=_decode_trust_panic(data["trust_panic"]),
            furnace=_decode_furnace(data["furnace"]),
            buildings=_decode_buildings(data["buildings"]),
            laws=_decode_laws(data["laws"]),
            technologies=_decode_technologies(data["technologies"]),
            events=_decode_events(data["events"]),
            promises=_decode_promises(data["promises"]),
            old_city=_decode_old_city(data["old_city"]),
            final_result=_decode_final_result(data["final_result"]),
        )
    except SaveDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise SaveDataError(f"invalid save data: {exc}") from exc


def validate_game_state(state: GameState) -> None:
    """Validate an in-memory state with the same rules used at the save boundary."""

    if not isinstance(state, GameState):
        raise SaveDataError("state must be GameState")
    hard_fail_type = state.final_result.hard_fail_type
    if hard_fail_type is not None and not isinstance(hard_fail_type, HardFailType):
        raise SaveDataError("final_result.hard_fail_type must use HardFailType")
    try:
        restored = decode_game_state(encode_game_state(state))
    except SaveDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise SaveDataError(f"invalid game state: {exc}") from exc
    if restored != state:
        raise SaveDataError("game state does not match the canonical runtime schema")
