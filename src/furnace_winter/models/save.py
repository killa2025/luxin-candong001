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
    OVERTIME_BUILDING_TYPES,
    BuildingManagementState,
    BuildingState,
    CalendarState,
    DailySurvivalState,
    EventRecord,
    EventResolutionRecord,
    EventState,
    FinalResultState,
    FurnaceState,
    GameState,
    HardFailType,
    HousingState,
    HungerState,
    LawState,
    MedicalState,
    OldCityState,
    PopulationState,
    PromiseRecord,
    PromiseSettlementRecord,
    PromiseState,
    ResourceState,
    SocialPolicyState,
    SurfaceResourcePointState,
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


_PATCH_006_DAILY_FIELDS = frozenset(
    {
        "target_overload_level",
        "effective_overload_level",
        "overload_coal_paid",
        "overload_temperature_bonus",
    }
)
_V6_DAILY_SURVIVAL_FIELDS = tuple(
    name
    for name in _field_names(DailySurvivalState)
    if name not in _PATCH_006_DAILY_FIELDS
)


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


def _integer_object(value: Any, path: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise SaveDataError(f"{path} must be an object")
    result: dict[str, int] = {}
    for key, item in value.items():
        checked_key = _string(key, f"{path} key")
        assert isinstance(checked_key, str)
        result[checked_key] = _integer(item, f"{path}.{checked_key}")
    return result


def _string_map(value: Any, path: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise SaveDataError(f"{path} must be an object")
    result: dict[str, str] = {}
    for key, item in value.items():
        checked_key = _string(key, f"{path} key")
        checked_value = _string(item, f"{path}.{checked_key}")
        assert isinstance(checked_key, str) and isinstance(checked_value, str)
        result[checked_key] = checked_value
    return result


def _raise_array(path: str) -> list[int]:
    raise SaveDataError(f"{path} must be an array")


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
    state = FurnaceState(
        is_active=_boolean(data["is_active"], "furnace.is_active"),
        mode_id=_string(data["mode_id"], "furnace.mode_id"),
        pressure=_integer(data["pressure"], "furnace.pressure", minimum=0),
        overload_level=_integer(
            data["overload_level"], "furnace.overload_level", minimum=0, maximum=2
        ),
        pressure_redline_warned=_boolean(
            data["pressure_redline_warned"], "furnace.pressure_redline_warned"
        ),
    )
    if state.mode_id not in {"off", "level_1", "level_2", "level_3"}:
        raise SaveDataError(f"unsupported furnace.mode_id: {state.mode_id}")
    if state.is_active != (state.mode_id != "off"):
        raise SaveDataError("furnace.is_active must match furnace.mode_id")
    return state


def _decode_housing(value: Any) -> HousingState:
    data = _object(value, "housing", _field_names(HousingState))
    return HousingState(
        basic_residences=_integer(
            data["basic_residences"], "housing.basic_residences", minimum=0
        ),
        capacity=_integer(data["capacity"], "housing.capacity", minimum=0),
    )


def _decode_hunger(value: Any) -> HungerState:
    data = _object(value, "hunger", _field_names(HungerState))
    return HungerState(
        mild_population=_integer(
            data["mild_population"], "hunger.mild_population", minimum=0
        ),
        severe_population=_integer(
            data["severe_population"], "hunger.severe_population", minimum=0
        ),
        starving_population=_integer(
            data["starving_population"], "hunger.starving_population", minimum=0
        ),
    )


def _decode_daily_survival(value: Any) -> DailySurvivalState:
    data = _object(value, "daily_survival", _field_names(DailySurvivalState))
    settled_day_value = data["settled_day"]
    settled_day = (
        None
        if settled_day_value is None
        else _integer(settled_day_value, "daily_survival.settled_day", minimum=1)
    )
    base_temperature_value = data["base_temperature"]
    base_temperature = (
        None
        if base_temperature_value is None
        else _integer(base_temperature_value, "daily_survival.base_temperature")
    )
    zone_temperatures = {
        key: _integer(item, f"daily_survival.zone_temperatures.{key}")
        for key, item in _integer_object(
            data["zone_temperatures"], "daily_survival.zone_temperatures"
        ).items()
    }
    return DailySurvivalState(
        settled_day=settled_day,
        base_temperature=base_temperature,
        target_furnace_level=_integer(
            data["target_furnace_level"],
            "daily_survival.target_furnace_level",
            minimum=0,
            maximum=3,
        ),
        effective_furnace_level=_integer(
            data["effective_furnace_level"],
            "daily_survival.effective_furnace_level",
            minimum=0,
            maximum=3,
        ),
        required_coal=_integer(
            data["required_coal"], "daily_survival.required_coal", minimum=0
        ),
        coal_paid=_integer(
            data["coal_paid"], "daily_survival.coal_paid", minimum=0
        ),
        woodfuel_wood_burned=_integer(
            data["woodfuel_wood_burned"],
            "daily_survival.woodfuel_wood_burned",
            minimum=0,
        ),
        woodfuel_contribution=_integer(
            data["woodfuel_contribution"],
            "daily_survival.woodfuel_contribution",
            minimum=0,
        ),
        target_overload_level=_integer(
            data["target_overload_level"],
            "daily_survival.target_overload_level",
            minimum=0,
            maximum=2,
        ),
        effective_overload_level=_integer(
            data["effective_overload_level"],
            "daily_survival.effective_overload_level",
            minimum=0,
            maximum=2,
        ),
        overload_coal_paid=_integer(
            data["overload_coal_paid"],
            "daily_survival.overload_coal_paid",
            minimum=0,
        ),
        overload_temperature_bonus=_integer(
            data["overload_temperature_bonus"],
            "daily_survival.overload_temperature_bonus",
            minimum=0,
        ),
        heating_shortfall=_boolean(
            data["heating_shortfall"], "daily_survival.heating_shortfall"
        ),
        zone_temperatures=zone_temperatures,
        ration_mode_used=_string(
            data["ration_mode_used"], "daily_survival.ration_mode_used"
        ),
        food_required=_integer(
            data["food_required"], "daily_survival.food_required", minimum=0
        ),
        cooked_food_eaten=_integer(
            data["cooked_food_eaten"],
            "daily_survival.cooked_food_eaten",
            minimum=0,
        ),
        raw_food_eaten=_integer(
            data["raw_food_eaten"], "daily_survival.raw_food_eaten", minimum=0
        ),
        food_shortfall=_integer(
            data["food_shortfall"], "daily_survival.food_shortfall", minimum=0
        ),
        unfed_population=_integer(
            data["unfed_population"],
            "daily_survival.unfed_population",
            minimum=0,
        ),
        worktime_sick_added=_integer(
            data["worktime_sick_added"],
            "daily_survival.worktime_sick_added",
            minimum=0,
        ),
        overtime_accident_risk_points=_integer(
            data["overtime_accident_risk_points"],
            "daily_survival.overtime_accident_risk_points",
            minimum=0,
        ),
        storage_used=_integer(
            data["storage_used"], "daily_survival.storage_used", minimum=0
        ),
        is_over_capacity=_boolean(
            data["is_over_capacity"], "daily_survival.is_over_capacity"
        ),
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
        bound_resource_id=_string(
            data["bound_resource_id"],
            f"{path}.bound_resource_id",
            optional=True,
        ),
        production_remainder_numerator=_integer(
            data["production_remainder_numerator"],
            f"{path}.production_remainder_numerator",
            minimum=0,
        ),
        production_multiplier_remainder_numerator=_integer(
            data["production_multiplier_remainder_numerator"],
            f"{path}.production_multiplier_remainder_numerator",
            minimum=0,
        ),
        production_multiplier_remainder_denominator=_integer(
            data["production_multiplier_remainder_denominator"],
            f"{path}.production_multiplier_remainder_denominator",
            minimum=1,
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


def _decode_surface_resource_point(
    value: Any, path: str, expected_id: str
) -> SurfaceResourcePointState:
    data = _object(value, path, _field_names(SurfaceResourcePointState))
    resource_point_id = _string(
        data["resource_point_id"], f"{path}.resource_point_id"
    )
    if resource_point_id != expected_id:
        raise SaveDataError(f"{path}.resource_point_id must match its map key")
    resource_type = _string(data["resource_type"], f"{path}.resource_type")
    if resource_type not in {"coal", "wood", "steel"}:
        raise SaveDataError(f"unsupported surface resource type: {resource_type}")
    return SurfaceResourcePointState(
        resource_point_id=resource_point_id,
        resource_type=resource_type,
        remaining_amount=_integer(
            data["remaining_amount"], f"{path}.remaining_amount", minimum=0
        ),
        staff_capacity=_integer(
            data["staff_capacity"], f"{path}.staff_capacity", minimum=1
        ),
        assigned_workers=_integer(
            data["assigned_workers"], f"{path}.assigned_workers", minimum=0
        ),
        assigned_engineers=_integer(
            data["assigned_engineers"], f"{path}.assigned_engineers", minimum=0
        ),
        production_remainder_numerator=_integer(
            data["production_remainder_numerator"],
            f"{path}.production_remainder_numerator",
            minimum=0,
        ),
        is_depleted=_boolean(data["is_depleted"], f"{path}.is_depleted"),
    )


def _decode_surface_resource_points(
    value: Any,
) -> dict[str, SurfaceResourcePointState]:
    if not isinstance(value, Mapping):
        raise SaveDataError("surface_resource_points must be an object")
    result: dict[str, SurfaceResourcePointState] = {}
    for key, item in value.items():
        resource_point_id = _string(key, "surface_resource_points key")
        assert isinstance(resource_point_id, str)
        result[resource_point_id] = _decode_surface_resource_point(
            item,
            f"surface_resource_points.{resource_point_id}",
            resource_point_id,
        )
    return result


def _decode_building_management(value: Any) -> BuildingManagementState:
    data = _object(value, "building_management", _field_names(BuildingManagementState))
    return BuildingManagementState(
        zone_slot_capacity=_nonnegative_int_object(
            data["zone_slot_capacity"], "building_management.zone_slot_capacity"
        ),
        zone_slots_used=_nonnegative_int_object(
            data["zone_slots_used"], "building_management.zone_slots_used"
        ),
        next_building_sequence=_integer(
            data["next_building_sequence"],
            "building_management.next_building_sequence",
            minimum=1,
        ),
        available_hunting_areas=_integer(
            data["available_hunting_areas"],
            "building_management.available_hunting_areas",
            minimum=1,
        ),
        total_hunting_areas=_integer(
            data["total_hunting_areas"],
            "building_management.total_hunting_areas",
            minimum=1,
        ),
        forest_zones=_integer(
            data["forest_zones"], "building_management.forest_zones", minimum=0
        ),
        woodfuel_confirmed_today=_boolean(
            data["woodfuel_confirmed_today"],
            "building_management.woodfuel_confirmed_today",
        ),
        heat_uses_today=_integer(
            data["heat_uses_today"],
            "building_management.heat_uses_today",
            minimum=0,
        ),
    )


def _decode_laws(value: Any) -> LawState:
    data = _object(value, "laws", _field_names(LawState))
    return LawState(
        signed_law_ids=_string_list(data["signed_law_ids"], "laws.signed_law_ids"),
        active_law_ids=_string_list(data["active_law_ids"], "laws.active_law_ids"),
        cooldowns=_nonnegative_int_object(data["cooldowns"], "laws.cooldowns"),
    )


def _decode_social_policy(value: Any) -> SocialPolicyState:
    data = _object(value, "social_policy", _field_names(SocialPolicyState))
    return SocialPolicyState(
        current_ration_mode=_string(
            data["current_ration_mode"], "social_policy.current_ration_mode"
        ),
        ration_food_numerator=_integer(
            data["ration_food_numerator"],
            "social_policy.ration_food_numerator",
            minimum=1,
        ),
        ration_food_denominator=_integer(
            data["ration_food_denominator"],
            "social_policy.ration_food_denominator",
            minimum=1,
        ),
        previous_ration_mode=_string(
            data["previous_ration_mode"],
            "social_policy.previous_ration_mode",
            optional=True,
        ),
        previous_ration_days=_integer(
            data["previous_ration_days"],
            "social_policy.previous_ration_days",
            minimum=0,
        ),
        consecutive_ration_days=_integer(
            data["consecutive_ration_days"],
            "social_policy.consecutive_ration_days",
            minimum=0,
        ),
        consecutive_ration_mode=_string(
            data["consecutive_ration_mode"],
            "social_policy.consecutive_ration_mode",
        ),
        current_worktime_mode=_string(
            data["current_worktime_mode"], "social_policy.current_worktime_mode"
        ),
        worktime_output_numerator=_integer(
            data["worktime_output_numerator"],
            "social_policy.worktime_output_numerator",
            minimum=1,
        ),
        worktime_output_denominator=_integer(
            data["worktime_output_denominator"],
            "social_policy.worktime_output_denominator",
            minimum=1,
        ),
        consecutive_long_shift_days=_integer(
            data["consecutive_long_shift_days"],
            "social_policy.consecutive_long_shift_days",
            minimum=0,
        ),
        overtime_building_id=_string(
            data["overtime_building_id"],
            "social_policy.overtime_building_id",
            optional=True,
        ),
        overtime_output_numerator=_integer(
            data["overtime_output_numerator"],
            "social_policy.overtime_output_numerator",
            minimum=1,
        ),
        overtime_output_denominator=_integer(
            data["overtime_output_denominator"],
            "social_policy.overtime_output_denominator",
            minimum=1,
        ),
        firepit_enabled=_boolean(
            data["firepit_enabled"], "social_policy.firepit_enabled"
        ),
        death_path=_string(data["death_path"], "social_policy.death_path"),
        unhandled_bodies=_integer(
            data["unhandled_bodies"], "social_policy.unhandled_bodies", minimum=0
        ),
        buried_bodies=_integer(
            data["buried_bodies"], "social_policy.buried_bodies", minimum=0
        ),
        stored_bodies=_integer(
            data["stored_bodies"], "social_policy.stored_bodies", minimum=0
        ),
        triage_building_id=_string(
            data["triage_building_id"],
            "social_policy.triage_building_id",
            optional=True,
        ),
        triage_used_ever=_boolean(
            data["triage_used_ever"], "social_policy.triage_used_ever"
        ),
        ending_tag_candidates=_string_list(
            data["ending_tag_candidates"], "social_policy.ending_tag_candidates"
        ),
    )


def _decode_medical(value: Any) -> MedicalState:
    data = _object(value, "medical", _field_names(MedicalState))
    return MedicalState(
        **{
            name: _integer(data[name], f"medical.{name}", minimum=0)
            for name in _field_names(MedicalState)
        }
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
        research_progress_units=_integer(
            data["research_progress_units"],
            "technologies.research_progress_units",
            minimum=0,
        ),
        research_required_units=_integer(
            data["research_required_units"],
            "technologies.research_required_units",
            minimum=0,
        ),
    )


def _decode_events(value: Any) -> EventState:
    data = _object(value, "events", _field_names(EventState))
    raw_active = data["active_events"]
    if not isinstance(raw_active, Mapping):
        raise SaveDataError("events.active_events must be an object")
    active_events: dict[str, EventRecord] = {}
    for raw_id, raw_event in raw_active.items():
        event_id = _string(raw_id, "events.active_events key")
        assert isinstance(event_id, str)
        item = _object(
            raw_event,
            f"events.active_events.{event_id}",
            _field_names(EventRecord),
        )
        stored_id = _string(
            item["event_id"], f"events.active_events.{event_id}.event_id"
        )
        if stored_id != event_id:
            raise SaveDataError("active event id must match its map key")
        active_events[event_id] = EventRecord(
            event_id=event_id,
            event_type=_string(
                item["event_type"],
                f"events.active_events.{event_id}.event_type",
            ),
            trigger_day=_integer(
                item["trigger_day"],
                f"events.active_events.{event_id}.trigger_day",
                minimum=1,
                maximum=FINAL_DAY,
            ),
            priority=_integer(
                item["priority"],
                f"events.active_events.{event_id}.priority",
                minimum=1,
            ),
            trigger_reason_ids=_string_list(
                item["trigger_reason_ids"],
                f"events.active_events.{event_id}.trigger_reason_ids",
            ),
            option_ids=_string_list(
                item["option_ids"],
                f"events.active_events.{event_id}.option_ids",
            ),
            is_blocking=_boolean(
                item["is_blocking"],
                f"events.active_events.{event_id}.is_blocking",
            ),
        )
    raw_history = data["resolution_history"]
    if not isinstance(raw_history, list):
        raise SaveDataError("events.resolution_history must be an array")
    resolution_history: list[EventResolutionRecord] = []
    for index, raw_record in enumerate(raw_history):
        path = f"events.resolution_history[{index}]"
        item = _object(raw_record, path, _field_names(EventResolutionRecord))
        resolution_history.append(
            EventResolutionRecord(
                event_id=_string(item["event_id"], f"{path}.event_id"),
                option_id=_string(item["option_id"], f"{path}.option_id"),
                event_type=_string(item["event_type"], f"{path}.event_type"),
                resolved_day=_integer(
                    item["resolved_day"], f"{path}.resolved_day", minimum=1, maximum=FINAL_DAY
                ),
                trust_change=(
                    None
                    if item["trust_change"] is None
                    else _integer(item["trust_change"], f"{path}.trust_change")
                ),
                panic_change=(
                    None
                    if item["panic_change"] is None
                    else _integer(item["panic_change"], f"{path}.panic_change")
                ),
                population_added=_integer(
                    item["population_added"], f"{path}.population_added", minimum=0
                ),
                resource_changes=_integer_object(
                    item["resource_changes"], f"{path}.resource_changes"
                ),
            )
        )
    return EventState(
        active_events=active_events,
        resolved_event_ids=_string_list(
            data["resolved_event_ids"], "events.resolved_event_ids"
        ),
        resolution_history=resolution_history,
        occurrence_counts=_nonnegative_int_object(
            data["occurrence_counts"], "events.occurrence_counts"
        ),
        cooldown_until_day=_nonnegative_int_object(
            data["cooldown_until_day"], "events.cooldown_until_day"
        ),
        suppressed_event_ids_today=_string_list(
            data["suppressed_event_ids_today"],
            "events.suppressed_event_ids_today",
        ),
        status_ids=_string_list(data["status_ids"], "events.status_ids"),
        generated_for_day=(
            None
            if data["generated_for_day"] is None
            else _integer(
                data["generated_for_day"],
                "events.generated_for_day",
                minimum=1,
                maximum=FINAL_DAY,
            )
        ),
        metrics=_integer_object(data["metrics"], "events.metrics"),
        recent_raw_food_days=[
            _integer(item, f"events.recent_raw_food_days[{index}]", minimum=1, maximum=FINAL_DAY)
            for index, item in enumerate(data["recent_raw_food_days"])
        ] if isinstance(data["recent_raw_food_days"], list) else _raise_array("events.recent_raw_food_days"),
        recent_canteen_outage_days=[
            _integer(item, f"events.recent_canteen_outage_days[{index}]", minimum=1, maximum=FINAL_DAY)
            for index, item in enumerate(data["recent_canteen_outage_days"])
        ] if isinstance(data["recent_canteen_outage_days"], list) else _raise_array("events.recent_canteen_outage_days"),
        recent_overtime_days=[
            _integer(item, f"events.recent_overtime_days[{index}]", minimum=1, maximum=FINAL_DAY)
            for index, item in enumerate(data["recent_overtime_days"])
        ] if isinstance(data["recent_overtime_days"], list) else _raise_array("events.recent_overtime_days"),
        fixed_arrival_choices=_string_map(
            data["fixed_arrival_choices"], "events.fixed_arrival_choices"
        ),
        frostfall_warning_stage=_string(
            data["frostfall_warning_stage"], "events.frostfall_warning_stage"
        ),
        frostfall_eve_status_shown=_boolean(
            data["frostfall_eve_status_shown"],
            "events.frostfall_eve_status_shown",
        ),
        seventh_frostfall_active=_boolean(
            data["seventh_frostfall_active"],
            "events.seventh_frostfall_active",
        ),
        hidden_achievements_unlocked=_string_list(
            data["hidden_achievements_unlocked"],
            "events.hidden_achievements_unlocked",
        ),
        hidden_achievement_popup_queue=_string_list(
            data["hidden_achievement_popup_queue"],
            "events.hidden_achievement_popup_queue",
        ),
        cold_exposure_deaths_total=_integer(
            data["cold_exposure_deaths_total"],
            "events.cold_exposure_deaths_total",
            minimum=0,
        ),
        deaths_today_by_cause=_nonnegative_int_object(
            data["deaths_today_by_cause"], "events.deaths_today_by_cause"
        ),
    )


def _decode_promises(value: Any) -> PromiseState:
    data = _object(value, "promises", _field_names(PromiseState))
    raw_active = data["active_promises"]
    if not isinstance(raw_active, Mapping):
        raise SaveDataError("promises.active_promises must be an object")
    active_promises: dict[str, PromiseRecord] = {}
    for raw_id, raw_promise in raw_active.items():
        promise_id = _string(raw_id, "promises.active_promises key")
        assert isinstance(promise_id, str)
        item = _object(
            raw_promise,
            f"promises.active_promises.{promise_id}",
            _field_names(PromiseRecord),
        )
        if item["promise_id"] != promise_id:
            raise SaveDataError("active promise id must match its map key")
        active_promises[promise_id] = PromiseRecord(
            promise_id=promise_id,
            promise_type=_string(item["promise_type"], f"promises.active_promises.{promise_id}.promise_type"),
            source_event_id=_string(item["source_event_id"], f"promises.active_promises.{promise_id}.source_event_id"),
            created_day=_integer(item["created_day"], f"promises.active_promises.{promise_id}.created_day", minimum=1, maximum=FINAL_DAY),
            deadline_day=_integer(item["deadline_day"], f"promises.active_promises.{promise_id}.deadline_day", minimum=1, maximum=FINAL_DAY),
            severity=_string(item["severity"], f"promises.active_promises.{promise_id}.severity"),
            target=_integer_object(item["target"], f"promises.active_promises.{promise_id}.target"),
        )
    raw_history = data["settlement_history"]
    if not isinstance(raw_history, list):
        raise SaveDataError("promises.settlement_history must be an array")
    settlement_history: list[PromiseSettlementRecord] = []
    for index, raw_record in enumerate(raw_history):
        path = f"promises.settlement_history[{index}]"
        item = _object(raw_record, path, _field_names(PromiseSettlementRecord))
        settlement_history.append(
            PromiseSettlementRecord(
                promise_id=_string(item["promise_id"], f"{path}.promise_id"),
                promise_type=_string(
                    item["promise_type"], f"{path}.promise_type"
                ),
                settled_day=_integer(
                    item["settled_day"], f"{path}.settled_day", minimum=1, maximum=FINAL_DAY
                ),
                outcome=_string(item["outcome"], f"{path}.outcome"),
                severity=_string(item["severity"], f"{path}.severity"),
                trust_change=_integer(
                    item["trust_change"], f"{path}.trust_change"
                ),
                panic_change=_integer(
                    item["panic_change"], f"{path}.panic_change"
                ),
            )
        )
    return PromiseState(
        active_promises=active_promises,
        completed_promise_ids=_string_list(
            data["completed_promise_ids"], "promises.completed_promise_ids"
        ),
        failed_promise_ids=_string_list(
            data["failed_promise_ids"], "promises.failed_promise_ids"
        ),
        settlement_history=settlement_history,
        next_sequence=_integer(
            data["next_sequence"], "promises.next_sequence", minimum=1
        ),
    )


def _decode_old_city(value: Any) -> OldCityState:
    data = _object(value, "old_city", _field_names(OldCityState))
    return OldCityState(
        is_unlocked=_boolean(data["is_unlocked"], "old_city.is_unlocked"),
        active_stage_id=_string(
            data["active_stage_id"], "old_city.active_stage_id", optional=True
        ),
        trigger_day=_integer(
            data["trigger_day"], "old_city.trigger_day", minimum=1, maximum=FINAL_DAY
        ),
        activation_pending=_boolean(
            data["activation_pending"], "old_city.activation_pending"
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
    if migrations is None:
        migrations = SaveMigrationRegistry()
        migrations.register(1, _migrate_v1_to_v2)
        migrations.register(2, _migrate_v2_to_v3)
        migrations.register(3, _migrate_v3_to_v4)
        migrations.register(4, _migrate_v4_to_v5)
        migrations.register(5, _migrate_v5_to_v6)
        migrations.register(6, _migrate_v6_to_v7)
        migrations.register(7, _migrate_v7_to_v8)
    data = migrations.migrate(document)
    data = _object(data, "$", _field_names(GameState))
    try:
        save_data_version = _integer(
            data["save_data_version"], "save_data_version", minimum=1
        )
        if save_data_version != CURRENT_SAVE_DATA_VERSION:
            raise SaveDataError(
                f"save version {save_data_version} does not match current schema"
            )
        state = GameState(
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
            housing=_decode_housing(data["housing"]),
            hunger=_decode_hunger(data["hunger"]),
            daily_survival=_decode_daily_survival(data["daily_survival"]),
            trust_panic=_decode_trust_panic(data["trust_panic"]),
            furnace=_decode_furnace(data["furnace"]),
            buildings=_decode_buildings(data["buildings"]),
            surface_resource_points=_decode_surface_resource_points(
                data["surface_resource_points"]
            ),
            building_management=_decode_building_management(
                data["building_management"]
            ),
            laws=_decode_laws(data["laws"]),
            social_policy=_decode_social_policy(data["social_policy"]),
            medical=_decode_medical(data["medical"]),
            technologies=_decode_technologies(data["technologies"]),
            events=_decode_events(data["events"]),
            promises=_decode_promises(data["promises"]),
            old_city=_decode_old_city(data["old_city"]),
            final_result=_decode_final_result(data["final_result"]),
        )
        _validate_state_invariants(state)
        return state
    except SaveDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise SaveDataError(f"invalid save data: {exc}") from exc


def _migrate_v1_to_v2(document: dict[str, Any]) -> dict[str, Any]:
    source = deepcopy(document)
    source.pop("social_policy", None)
    source.pop("medical", None)
    v2_only_fields = {
        "housing",
        "hunger",
        "daily_survival",
        "building_management",
        "surface_resource_points",
        "social_policy",
        "medical",
    }
    legacy = _object(source, "$", set(_field_names(GameState)) - v2_only_fields)
    legacy_furnace = _object(
        legacy["furnace"],
        "furnace",
        {"is_active", "mode_id", "pressure"},
    )
    furnace_active = _boolean(legacy_furnace["is_active"], "furnace.is_active")
    _string(legacy_furnace["mode_id"], "furnace.mode_id", optional=True)
    _integer(legacy_furnace["pressure"], "furnace.pressure", minimum=0)

    migrated = deepcopy(legacy)
    population = migrated.get("population")
    housed = 0
    if isinstance(population, Mapping):
        housed_value = population.get("housed_population", 0)
        if isinstance(housed_value, int) and not isinstance(housed_value, bool):
            housed = max(housed_value, 0)
    migrated["housing"] = {"basic_residences": 0, "capacity": housed}
    migrated["hunger"] = {
        "mild_population": 0,
        "severe_population": 0,
        "starving_population": 0,
    }
    migrated["daily_survival"] = {
        "settled_day": None,
        "base_temperature": None,
        "target_furnace_level": 0,
        "effective_furnace_level": 0,
        "required_coal": 0,
        "coal_paid": 0,
        "heating_shortfall": False,
        "zone_temperatures": {},
        "cooked_food_eaten": 0,
        "raw_food_eaten": 0,
        "unfed_population": 0,
        "storage_used": 0,
        "is_over_capacity": False,
    }
    furnace = migrated.get("furnace")
    if isinstance(furnace, Mapping):
        normalized = dict(furnace)
        normalized["mode_id"] = "level_1" if furnace_active else "off"
        migrated["furnace"] = normalized
    migrated["save_data_version"] = 2
    return migrated


def _migrate_v2_to_v3(document: dict[str, Any]) -> dict[str, Any]:
    source = deepcopy(document)
    source.pop("social_policy", None)
    source.pop("medical", None)
    legacy = _object(
        source,
        "$",
        set(_field_names(GameState))
        - {"building_management", "surface_resource_points", "social_policy", "medical"},
    )
    migrated = deepcopy(legacy)

    raw_daily = migrated["daily_survival"]
    if not isinstance(raw_daily, Mapping):
        raise SaveDataError("daily_survival must be an object")
    normalized_daily = dict(raw_daily)
    for future_field in (
        "ration_mode_used",
        "food_required",
        "food_shortfall",
        "worktime_sick_added",
        "overtime_accident_risk_points",
    ):
        normalized_daily.pop(future_field, None)
    daily = _object(
        normalized_daily,
        "daily_survival",
        set(_V6_DAILY_SURVIVAL_FIELDS)
        - {
            "woodfuel_wood_burned",
            "woodfuel_contribution",
            "ration_mode_used",
            "food_required",
            "food_shortfall",
            "worktime_sick_added",
            "overtime_accident_risk_points",
        },
    )
    daily["woodfuel_wood_burned"] = 0
    daily["woodfuel_contribution"] = 0
    migrated["daily_survival"] = daily

    raw_buildings = migrated.get("buildings")
    if not isinstance(raw_buildings, Mapping):
        raise SaveDataError("buildings must be an object")
    buildings: dict[str, Any] = {}
    old_building_fields = set(_field_names(BuildingState)) - {
        "bound_resource_id",
        "production_remainder_numerator",
        "production_multiplier_remainder_numerator",
        "production_multiplier_remainder_denominator",
    }
    for key, raw_building in raw_buildings.items():
        building = _object(raw_building, f"buildings.{key}", old_building_fields)
        building["bound_resource_id"] = None
        buildings[key] = building

    housing = migrated.get("housing")
    basic_residences = 0
    if isinstance(housing, Mapping):
        value = housing.get("basic_residences", 0)
        if isinstance(value, int) and not isinstance(value, bool):
            basic_residences = max(value, 0)
    represented_residences = sum(
        1
        for building in buildings.values()
        if isinstance(building, Mapping)
        and building.get("building_type") == "basic_residence"
    )
    missing_residences = max(basic_residences - represented_residences, 0)
    candidate_index = 1
    for _ in range(missing_residences):
        while True:
            building_id = f"residence-start-{candidate_index:03d}"
            candidate_index += 1
            if building_id not in buildings:
                break
        buildings[building_id] = {
            "building_id": building_id,
            "building_type": "basic_residence",
            "zone": "inner_ring",
            "slot_size": 1,
            "is_built": True,
            "is_operational": True,
            "assigned_workers": 0,
            "assigned_engineers": 0,
            "assigned_children": 0,
            "assigned_medical_apprentices": 0,
            "assigned_engineering_apprentices": 0,
            "can_heat": False,
            "heated_today": False,
            "effective_temperature": 0,
            "is_shutdown_by_temperature": False,
            "bound_resource_id": None,
        }
    migrated["buildings"] = buildings

    slot_capacity = {
        "inner_ring": 18,
        "middle_ring": 30,
        "outer_ring": 36,
        "storage_outer": 12,
    }
    slots_used = {zone: 0 for zone in slot_capacity}
    for building in buildings.values():
        if not isinstance(building, Mapping):
            continue
        zone = building.get("zone")
        size = building.get("slot_size")
        if zone in slots_used and isinstance(size, int) and not isinstance(size, bool):
            slots_used[zone] += max(size, 0)
    migrated["building_management"] = {
        "zone_slot_capacity": slot_capacity,
        "zone_slots_used": slots_used,
        "next_building_sequence": 1,
        "available_hunting_areas": 1,
        "total_hunting_areas": 2,
        "forest_zones": 2,
        "woodfuel_confirmed_today": False,
    }
    migrated["save_data_version"] = 3
    return migrated


def _migrate_v3_to_v4(document: dict[str, Any]) -> dict[str, Any]:
    source = deepcopy(document)
    source.pop("social_policy", None)
    source.pop("medical", None)
    legacy = _object(
        source,
        "$",
        set(_field_names(GameState)) - {"surface_resource_points", "social_policy", "medical"},
    )
    migrated = deepcopy(legacy)

    raw_buildings = migrated.get("buildings")
    if not isinstance(raw_buildings, Mapping):
        raise SaveDataError("buildings must be an object")
    buildings: dict[str, Any] = {}
    old_building_fields = set(_field_names(BuildingState)) - {
        "production_remainder_numerator",
        "production_multiplier_remainder_numerator",
        "production_multiplier_remainder_denominator",
    }
    for key, raw_building in raw_buildings.items():
        building = _object(raw_building, f"buildings.{key}", old_building_fields)
        building["production_remainder_numerator"] = 0
        buildings[key] = building
    migrated["buildings"] = buildings

    management = _object(
        migrated["building_management"],
        "building_management",
        set(_field_names(BuildingManagementState)) - {"heat_uses_today"},
    )
    management["heat_uses_today"] = 0
    migrated["building_management"] = management

    point_specs = {
        **{
            f"surface-coal-{index}": ("coal", 120, 15)
            for index in range(1, 5)
        },
        **{
            f"surface-wood-{index}": ("wood", 100, 15)
            for index in range(1, 6)
        },
        **{
            f"surface-steel-{index}": ("steel", 40, 10)
            for index in range(1, 4)
        },
    }
    migrated["surface_resource_points"] = {
        resource_point_id: {
            "resource_point_id": resource_point_id,
            "resource_type": resource_type,
            "remaining_amount": total_amount,
            "staff_capacity": staff_capacity,
            "assigned_workers": 0,
            "assigned_engineers": 0,
            "production_remainder_numerator": 0,
            "is_depleted": False,
        }
        for resource_point_id, (
            resource_type,
            total_amount,
            staff_capacity,
        ) in point_specs.items()
    }
    migrated["save_data_version"] = 4
    return migrated


def _migrate_v4_to_v5(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(
        document,
        "$",
        set(_field_names(GameState)) - {"social_policy", "medical"},
    )
    migrated = deepcopy(legacy)
    raw_buildings = migrated["buildings"]
    if not isinstance(raw_buildings, Mapping):
        raise SaveDataError("buildings must be an object")
    prepared_buildings: dict[str, dict[str, Any]] = {}
    for building_id, raw_building in raw_buildings.items():
        checked_id = _string(building_id, "buildings key")
        assert isinstance(checked_id, str)
        if not isinstance(raw_building, Mapping):
            raise SaveDataError(f"buildings.{checked_id} must be an object")
        building = dict(raw_building)
        building["production_multiplier_remainder_numerator"] = 0
        building["production_multiplier_remainder_denominator"] = 1
        prepared_buildings[checked_id] = building
    migrated["buildings"] = prepared_buildings
    decoded_buildings = _decode_buildings(prepared_buildings)

    raw_daily = migrated["daily_survival"]
    if not isinstance(raw_daily, Mapping):
        raise SaveDataError("daily_survival must be an object")
    daily = dict(raw_daily)
    cooked_eaten = _integer(
        daily.get("cooked_food_eaten"),
        "daily_survival.cooked_food_eaten",
        minimum=0,
    )
    raw_eaten = _integer(
        daily.get("raw_food_eaten"),
        "daily_survival.raw_food_eaten",
        minimum=0,
    )
    legacy_shortfall = _integer(
        daily.get("unfed_population"),
        "daily_survival.unfed_population",
        minimum=0,
    )
    daily["ration_mode_used"] = "normal"
    daily["food_required"] = cooked_eaten + raw_eaten + legacy_shortfall
    daily["food_shortfall"] = legacy_shortfall
    daily["worktime_sick_added"] = 0
    daily["overtime_accident_risk_points"] = 0
    _object(daily, "daily_survival", _V6_DAILY_SURVIVAL_FIELDS)
    migrated["daily_survival"] = daily

    calendar = _decode_calendar(migrated["calendar"])
    population = _decode_nonnegative_int_state(
        migrated["population"], "population", PopulationState
    )
    assert isinstance(population, PopulationState)
    temporary_capacity = 5 if calendar.current_day <= 3 else 0
    building_capacity = 0
    for building in decoded_buildings.values():
        if not building.is_operational:
            continue
        staff = (
            building.assigned_workers
            + building.assigned_engineers
            + building.assigned_children
            + building.assigned_medical_apprentices
            + building.assigned_engineering_apprentices
        )
        if building.building_type == "medical_station":
            building_capacity += (10 * staff) // 5
        elif building.building_type == "hospital":
            building_capacity += (30 * staff) // 10
    effective_capacity = temporary_capacity + building_capacity
    migrated["social_policy"] = {
        "current_ration_mode": "normal",
        "ration_food_numerator": 100,
        "ration_food_denominator": 100,
        "previous_ration_mode": None,
        "previous_ration_days": 0,
        "consecutive_ration_days": 0,
        "current_worktime_mode": "normal",
        "worktime_output_numerator": 100,
        "worktime_output_denominator": 100,
        "consecutive_long_shift_days": 0,
        "overtime_building_id": None,
        "overtime_output_numerator": 100,
        "overtime_output_denominator": 100,
        "firepit_enabled": False,
        "death_path": "none",
        "unhandled_bodies": 0,
        "buried_bodies": 0,
        "stored_bodies": 0,
        "triage_building_id": None,
        "triage_used_ever": False,
        "ending_tag_candidates": [],
    }
    migrated["medical"] = {
        "temporary_capacity": temporary_capacity,
        "building_capacity": building_capacity,
        "effective_capacity": effective_capacity,
        "medical_pressure": max(
            population.sick_population
            + population.critical_population
            - effective_capacity,
            0,
        ),
        "critical_treatment_progress": 0,
        "medical_ration_sick_cured_today": 0,
        "medical_ration_critical_progress_today": 0,
    }
    migrated["save_data_version"] = 5
    return migrated


def _migrate_v5_to_v6(document: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(document)
    social = _object(
        migrated.get("social_policy"),
        "social_policy",
        set(_field_names(SocialPolicyState)) - {"consecutive_ration_mode"},
    )
    current_mode = _string(
        social.get("current_ration_mode"), "social_policy.current_ration_mode"
    )
    previous_mode = _string(
        social.get("previous_ration_mode"),
        "social_policy.previous_ration_mode",
        optional=True,
    )
    consecutive_days = _integer(
        social.get("consecutive_ration_days"),
        "social_policy.consecutive_ration_days",
        minimum=0,
    )
    if consecutive_days == 0:
        consecutive_mode = "normal"
    elif current_mode in {"coarse_soup", "rice_porridge"}:
        consecutive_mode = current_mode
    elif current_mode == "emergency" and previous_mode in {
        "coarse_soup",
        "rice_porridge",
    }:
        consecutive_mode = previous_mode
    else:
        laws = _object(migrated.get("laws"), "laws", _field_names(LawState))
        signed = set(
            _string_list(laws.get("signed_law_ids"), "laws.signed_law_ids")
        )
        candidates = [
            mode
            for mode, law_id in (
                ("coarse_soup", "coarse_soup_law"),
                ("rice_porridge", "rice_porridge_law"),
            )
            if law_id in signed
        ]
        if len(candidates) != 1:
            raise SaveDataError(
                "v5 ration streak mode cannot be derived unambiguously"
            )
        consecutive_mode = candidates[0]
    social["consecutive_ration_mode"] = consecutive_mode
    migrated["social_policy"] = dict(social)
    migrated["save_data_version"] = 6
    return migrated


def _migrate_v6_to_v7(document: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(document)
    furnace = _object(
        migrated.get("furnace"),
        "furnace",
        ("is_active", "mode_id", "pressure"),
    )
    furnace["overload_level"] = 0
    pressure = _integer(furnace["pressure"], "furnace.pressure", minimum=0)
    furnace["pressure_redline_warned"] = pressure >= 100
    migrated["furnace"] = furnace

    added_daily_fields = _PATCH_006_DAILY_FIELDS
    daily = _object(
        migrated.get("daily_survival"),
        "daily_survival",
        _V6_DAILY_SURVIVAL_FIELDS,
    )
    for name in added_daily_fields:
        daily[name] = 0
    migrated["daily_survival"] = daily

    technologies = _object(
        migrated.get("technologies"),
        "technologies",
        ("researched_tech_ids", "active_research_id", "research_progress_days"),
    )
    progress_days = _integer(
        technologies.pop("research_progress_days"),
        "technologies.research_progress_days",
        minimum=0,
    )
    active_research_id = _string(
        technologies.get("active_research_id"),
        "technologies.active_research_id",
        optional=True,
    )
    if active_research_id is not None or progress_days != 0:
        raise SaveDataError(
            "v6 active research cannot be migrated before Patch 006 rules exist"
        )
    technologies["research_progress_units"] = 0
    technologies["research_required_units"] = 0
    migrated["technologies"] = technologies
    migrated["save_data_version"] = 7
    return migrated


def _migrate_v7_to_v8(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _field_names(GameState))
    migrated = deepcopy(legacy)
    if not isinstance(migrated["events"], Mapping):
        raise SaveDataError("events must be an object")
    raw_events = dict(migrated["events"])
    if "active_event_ids" in raw_events:
        events = _object(
            raw_events,
            "events",
            ("active_event_ids", "resolved_event_ids"),
        )
        if events["active_event_ids"]:
            raise SaveDataError(
                "v7 active event ids cannot be migrated without Patch 007 event records"
            )
        migrated["events"] = {
            "active_events": {},
            "resolved_event_ids": _string_list(
                events["resolved_event_ids"], "events.resolved_event_ids"
            ),
            "resolution_history": [],
            "occurrence_counts": {},
            "cooldown_until_day": {},
            "suppressed_event_ids_today": [],
            "status_ids": [],
            "generated_for_day": None,
            "metrics": {},
            "recent_raw_food_days": [],
            "recent_canteen_outage_days": [],
            "recent_overtime_days": [],
            "fixed_arrival_choices": {},
            "frostfall_warning_stage": "none",
            "frostfall_eve_status_shown": False,
            "seventh_frostfall_active": False,
            "hidden_achievements_unlocked": [],
            "hidden_achievement_popup_queue": [],
            "cold_exposure_deaths_total": 0,
            "deaths_today_by_cause": {},
        }
    else:
        # Some tests and importers build an older-version envelope around a
        # current empty state. Accept that already-expanded representation;
        # strict decoding after the migration still validates every field.
        migrated["events"] = _object(raw_events, "events", _field_names(EventState))

    if not isinstance(migrated["promises"], Mapping):
        raise SaveDataError("promises must be an object")
    raw_promises = dict(migrated["promises"])
    if "active_promise_ids" in raw_promises:
        promises = _object(
            raw_promises,
            "promises",
            (
                "active_promise_ids",
                "completed_promise_ids",
                "failed_promise_ids",
            ),
        )
        if promises["active_promise_ids"]:
            raise SaveDataError(
                "v7 active promise ids cannot be migrated without Patch 007 promise records"
            )
        migrated["promises"] = {
            "active_promises": {},
            "completed_promise_ids": _string_list(
                promises["completed_promise_ids"],
                "promises.completed_promise_ids",
            ),
            "failed_promise_ids": _string_list(
                promises["failed_promise_ids"], "promises.failed_promise_ids"
            ),
            "settlement_history": [],
            "next_sequence": 1,
        }
    else:
        migrated["promises"] = _object(
            raw_promises, "promises", _field_names(PromiseState)
        )

    if not isinstance(migrated["old_city"], Mapping):
        raise SaveDataError("old_city must be an object")
    raw_old_city = dict(migrated["old_city"])
    if set(raw_old_city) == {"is_unlocked", "active_stage_id"}:
        old_city = _object(
            raw_old_city,
            "old_city",
            ("is_unlocked", "active_stage_id"),
        )
        migrated["old_city"] = {
            **old_city,
            "trigger_day": 24,
            "activation_pending": False,
        }
    else:
        migrated["old_city"] = _object(
            raw_old_city, "old_city", _field_names(OldCityState)
        )
    migrated["save_data_version"] = 8
    return migrated


def _validate_state_invariants(state: GameState) -> None:
    population = state.population
    technologies = state.technologies
    events = state.events
    promises = state.promises
    if len(set(events.resolved_event_ids)) != len(events.resolved_event_ids):
        raise SaveDataError("resolved event ids must be unique")
    if len(set(events.suppressed_event_ids_today)) != len(
        events.suppressed_event_ids_today
    ):
        raise SaveDataError("suppressed event ids must be unique")
    if len(set(events.status_ids)) != len(events.status_ids):
        raise SaveDataError("event status ids must be unique")
    if set(events.active_events) & set(events.resolved_event_ids):
        raise SaveDataError("active and resolved events must be disjoint")
    for resolution in events.resolution_history:
        if resolution.event_id not in events.resolved_event_ids:
            raise SaveDataError("event history must reference a resolved event")
        if resolution.event_type not in {"major", "normal"}:
            raise SaveDataError("event history contains an unsupported event type")
        if resolution.resolved_day > state.calendar.current_day:
            raise SaveDataError("event history cannot come from a future day")
        if set(resolution.resource_changes) != {
            "coal", "wood", "steel", "raw_food", "cooked_food"
        }:
            raise SaveDataError("event history resource changes are incomplete")
    major_count = 0
    normal_count = 0
    for event_id, event in events.active_events.items():
        if event.event_id != event_id:
            raise SaveDataError("active event id must match its map key")
        if events.occurrence_counts.get(event_id, 0) < 1:
            raise SaveDataError("active events must be counted when displayed")
        if event.event_type not in {"major", "normal"}:
            raise SaveDataError("unsupported active event type")
        if event.trigger_day != state.calendar.current_day:
            raise SaveDataError("active events must belong to the current day")
        if len(set(event.option_ids)) != len(event.option_ids) or not event.option_ids:
            raise SaveDataError("active events must expose unique executable options")
        if event.is_blocking != (event.event_type == "major"):
            raise SaveDataError("only major events may block end_day")
        if event.event_type == "major":
            major_count += 1
        else:
            normal_count += 1
    if major_count > 1 or normal_count > (1 if major_count else 2):
        raise SaveDataError("active event queue exceeds the daily display limits")
    if events.generated_for_day is not None and events.generated_for_day != state.calendar.current_day:
        raise SaveDataError("generated event day must match the current day")
    if len(set(events.hidden_achievements_unlocked)) != len(
        events.hidden_achievements_unlocked
    ):
        raise SaveDataError("hidden achievements must be unique")
    if not set(events.hidden_achievement_popup_queue).issubset(
        events.hidden_achievements_unlocked
    ):
        raise SaveDataError("achievement popup queue must contain unlocked achievements")
    if events.frostfall_warning_stage not in {
        "none", "day34", "day42", "day46", "day48", "day49"
    }:
        raise SaveDataError("unsupported frostfall warning stage")
    if events.generated_for_day is not None:
        if events.seventh_frostfall_active != (state.calendar.current_day >= 49):
            raise SaveDataError("seventh frostfall flag must match the calendar")
    elif events.active_events:
        raise SaveDataError("active events require a generated event day")
    if set(events.fixed_arrival_choices) - {"arrival_day6", "arrival_day19", "arrival_day37"}:
        raise SaveDataError("unknown fixed arrival choice key")
    if any(choice not in {"accept_all", "accept_partial", "reject"} for choice in events.fixed_arrival_choices.values()):
        raise SaveDataError("unsupported fixed arrival choice")
    if len(promises.active_promises) > 2:
        raise SaveDataError("at most two promises may be active")
    active_types: set[str] = set()
    settled_promises = set(promises.completed_promise_ids) | set(promises.failed_promise_ids)
    if set(promises.completed_promise_ids) & set(promises.failed_promise_ids):
        raise SaveDataError("completed and failed promise ids must be disjoint")
    if len(set(promises.completed_promise_ids)) != len(promises.completed_promise_ids) or len(set(promises.failed_promise_ids)) != len(promises.failed_promise_ids):
        raise SaveDataError("settled promise ids must be unique")
    if set(promises.active_promises) & settled_promises:
        raise SaveDataError("active and settled promises must be disjoint")
    settlement_ids: set[str] = set()
    for settlement in promises.settlement_history:
        if settlement.promise_id in settlement_ids:
            raise SaveDataError("a promise may only be recorded as settled once")
        settlement_ids.add(settlement.promise_id)
        if settlement.outcome == "success":
            expected_ids = promises.completed_promise_ids
        elif settlement.outcome == "failure":
            expected_ids = promises.failed_promise_ids
        else:
            raise SaveDataError("unsupported promise settlement outcome")
        if settlement.promise_id not in expected_ids:
            raise SaveDataError("promise history disagrees with settled promise ids")
        if settlement.settled_day > state.calendar.current_day:
            raise SaveDataError("promise history cannot come from a future day")
    for promise_id, promise in promises.active_promises.items():
        if promise.promise_id != promise_id:
            raise SaveDataError("active promise id must match its map key")
        if promise.promise_type in active_types:
            raise SaveDataError("only one active promise of each type is allowed")
        active_types.add(promise.promise_type)
        if promise.severity not in {"ordinary", "serious", "critical"}:
            raise SaveDataError("unsupported promise severity")
        if promise.deadline_day < promise.created_day:
            raise SaveDataError("promise deadline cannot precede its creation day")
        if promise.created_day >= 49:
            raise SaveDataError("normal promises cannot be created during frostfall")
        if promise.created_day >= 42 and promise.deadline_day > 48:
            raise SaveDataError("late normal promise deadline cannot exceed day 48")
    if state.old_city.trigger_day != 24:
        raise SaveDataError("old city trigger interface must remain fixed at day 24")
    if state.old_city.activation_pending and state.calendar.current_day < 24:
        raise SaveDataError("old city activation cannot be pending before day 24")
    if state.old_city.is_unlocked and state.old_city.activation_pending:
        raise SaveDataError("unlocked old city state cannot remain activation-pending")
    if not state.old_city.is_unlocked and state.old_city.active_stage_id is not None:
        raise SaveDataError("locked old city state cannot have an active stage")
    if len(set(technologies.researched_tech_ids)) != len(
        technologies.researched_tech_ids
    ):
        raise SaveDataError("researched tech ids must be unique")
    if technologies.active_research_id is None:
        if (
            technologies.research_progress_units != 0
            or technologies.research_required_units != 0
        ):
            raise SaveDataError("inactive research must have zero progress and requirement")
    else:
        if technologies.active_research_id in technologies.researched_tech_ids:
            raise SaveDataError("active research must not already be completed")
        if technologies.research_required_units <= 0:
            raise SaveDataError("active research must have a positive requirement")
        if technologies.research_progress_units >= technologies.research_required_units:
            raise SaveDataError("active research progress must be below its requirement")
    if state.furnace.overload_level > 0 and not state.furnace.is_active:
        raise SaveDataError("furnace overload requires an active furnace")
    if state.furnace.pressure_redline_warned != (state.furnace.pressure >= 100):
        raise SaveDataError("furnace redline warning must match pressure threshold")
    if len(set(state.laws.signed_law_ids)) != len(state.laws.signed_law_ids):
        raise SaveDataError("signed law ids must be unique")
    if len(set(state.laws.active_law_ids)) != len(state.laws.active_law_ids):
        raise SaveDataError("active law ids must be unique")
    if not set(state.laws.active_law_ids).issubset(state.laws.signed_law_ids):
        raise SaveDataError("active laws must also be signed")
    if population.population_total != (
        population.population_alive + population.population_dead
    ):
        raise SaveDataError("population_total must equal alive plus dead")
    if population.population_alive != (
        population.healthy_population
        + population.sick_population
        + population.critical_population
        + population.disabled_population
    ):
        raise SaveDataError(
            "population_alive must equal healthy, sick, critical, and disabled pools"
        )
    occupation_total = population.workers + population.engineers + population.children
    if occupation_total > population.population_alive:
        raise SaveDataError("occupation and child pools must not exceed living population")
    if (
        population.medical_apprentices + population.engineering_apprentices
        > population.children
    ):
        raise SaveDataError("apprentices must remain a subset of children")

    expected_housed = min(population.population_alive, state.housing.capacity)
    if population.housed_population != expected_housed:
        raise SaveDataError("housed_population must match aggregate housing capacity")
    if population.homeless_population != population.population_alive - expected_housed:
        raise SaveDataError("homeless_population must match aggregate housing capacity")

    hunger_total = (
        state.hunger.mild_population
        + state.hunger.severe_population
        + state.hunger.starving_population
    )
    if hunger_total > population.population_alive:
        raise SaveDataError("hunger pools must not exceed living population")

    social = state.social_policy
    if social.current_ration_mode not in {
        "normal",
        "coarse_soup",
        "rice_porridge",
        "emergency",
    }:
        raise SaveDataError("unsupported ration mode")
    if social.ration_food_numerator <= 0 or social.ration_food_denominator <= 0:
        raise SaveDataError("ration food ratio must be positive")
    if social.previous_ration_mode not in {
        None,
        "normal",
        "coarse_soup",
        "rice_porridge",
    }:
        raise SaveDataError("unsupported previous ration mode")
    if (social.current_ration_mode == "emergency") != (
        social.previous_ration_mode is not None
    ):
        raise SaveDataError("emergency ration must retain exactly one previous mode")
    if (
        social.current_ration_mode == "emergency"
        and social.previous_ration_days != social.consecutive_ration_days
    ):
        raise SaveDataError(
            "emergency ration must preserve the current ration streak days"
        )
    if social.previous_ration_mode is None and social.previous_ration_days != 0:
        raise SaveDataError("inactive emergency ration cannot retain previous days")
    if social.consecutive_ration_mode not in {
        "normal",
        "coarse_soup",
        "rice_porridge",
    }:
        raise SaveDataError("unsupported consecutive ration mode")
    if social.consecutive_ration_days == 0 and social.consecutive_ration_mode != "normal":
        raise SaveDataError("zero ration streak must use the normal streak mode")
    if social.consecutive_ration_days > 0 and social.consecutive_ration_mode == "normal":
        raise SaveDataError("positive ration streak must use a nonstandard mode")
    if social.current_worktime_mode not in {"normal", "long_shift"}:
        raise SaveDataError("unsupported worktime mode")
    if min(
        social.worktime_output_numerator,
        social.worktime_output_denominator,
        social.overtime_output_numerator,
        social.overtime_output_denominator,
    ) <= 0:
        raise SaveDataError("work output ratios must be positive")
    if social.overtime_building_id is None and (
        social.overtime_output_numerator != 100
        or social.overtime_output_denominator != 100
    ):
        raise SaveDataError("inactive overtime must use the neutral output ratio")
    if social.death_path not in {"none", "cemetery", "cold_pit"}:
        raise SaveDataError("unsupported death path")
    accounted_bodies = (
        social.unhandled_bodies + social.buried_bodies + social.stored_bodies
    )
    if accounted_bodies > population.population_dead:
        raise SaveDataError("handled and unhandled bodies cannot exceed total deaths")
    if social.overtime_building_id is not None:
        if social.overtime_building_id not in state.buildings:
            raise SaveDataError("overtime target must be a registered building")
        overtime_target = state.buildings[social.overtime_building_id]
        if "overtime_law" not in state.laws.signed_law_ids:
            raise SaveDataError("overtime target requires the overtime law")
        if overtime_target.building_type not in OVERTIME_BUILDING_TYPES:
            raise SaveDataError("overtime target building type is not allowed")
        overtime_staff = sum(
            (
                overtime_target.assigned_workers,
                overtime_target.assigned_engineers,
                overtime_target.assigned_children,
                overtime_target.assigned_medical_apprentices,
                overtime_target.assigned_engineering_apprentices,
            )
        )
        if overtime_staff <= 0:
            raise SaveDataError("overtime target must retain assigned staff")
    if social.triage_building_id is not None and social.triage_building_id not in state.buildings:
        raise SaveDataError("triage target must be a registered building")
    if len(set(social.ending_tag_candidates)) != len(social.ending_tag_candidates):
        raise SaveDataError("ending tag candidates must be unique")

    medical = state.medical
    if medical.effective_capacity != medical.temporary_capacity + medical.building_capacity:
        raise SaveDataError("effective medical capacity must match its components")
    expected_pressure = max(
        population.sick_population + population.critical_population
        - medical.effective_capacity,
        0,
    )
    if medical.medical_pressure != expected_pressure:
        raise SaveDataError("medical pressure must match population and capacity")
    if medical.medical_ration_sick_cured_today > population.population_total:
        raise SaveDataError("medical ration cured count exceeds total population")
    if medical.medical_ration_critical_progress_today > population.population_total:
        raise SaveDataError("medical ration progress count exceeds total population")

    daily = state.daily_survival
    if daily.ration_mode_used not in {
        "normal",
        "coarse_soup",
        "rice_porridge",
        "emergency",
    }:
        raise SaveDataError("unsupported settled ration mode")
    food_eaten = daily.cooked_food_eaten + daily.raw_food_eaten
    if daily.food_shortfall != max(daily.food_required - food_eaten, 0):
        raise SaveDataError("food shortfall must match required and eaten food")
    if food_eaten > daily.food_required:
        raise SaveDataError("food eaten cannot exceed required food")
    if daily.unfed_population > population.population_total:
        raise SaveDataError("unfed population cannot exceed total population")
    if daily.effective_furnace_level > daily.target_furnace_level:
        raise SaveDataError("effective furnace level cannot exceed the target level")
    if daily.coal_paid > daily.required_coal:
        raise SaveDataError("coal_paid cannot exceed required_coal")
    if daily.woodfuel_wood_burned < daily.woodfuel_contribution:
        raise SaveDataError("woodfuel burned wood cannot be less than its contribution")
    if daily.heating_shortfall != (
        daily.effective_furnace_level < daily.target_furnace_level
        or daily.effective_overload_level < daily.target_overload_level
    ):
        raise SaveDataError(
            "heating_shortfall must match furnace and overload target levels"
        )
    if daily.effective_overload_level > daily.target_overload_level:
        raise SaveDataError("effective overload level cannot exceed its target")
    if (
        daily.settled_day is not None
        and daily.effective_overload_level not in {
            0,
            daily.target_overload_level,
        }
    ):
        raise SaveDataError(
            "settled effective overload must be zero or match its target"
        )
    if daily.effective_overload_level == 0 and (
        daily.overload_coal_paid != 0
        or daily.overload_temperature_bonus != 0
    ):
        raise SaveDataError("inactive daily overload must have zero payment and bonus")
    if (
        daily.effective_overload_level > 0
        and daily.effective_furnace_level == 0
    ):
        raise SaveDataError("effective daily overload requires effective base heating")
    if daily.settled_day is None:
        if (
            daily.base_temperature is not None
            or daily.zone_temperatures
            or daily.target_overload_level != 0
            or daily.effective_overload_level != 0
            or daily.overload_coal_paid != 0
            or daily.overload_temperature_bonus != 0
        ):
            raise SaveDataError(
                "unsettled survival summary cannot contain settlement effects"
            )
    else:
        if daily.base_temperature is None:
            raise SaveDataError("settled survival summary requires base_temperature")
        if set(daily.zone_temperatures) != {
            "inner_ring",
            "middle_ring",
            "outer_ring",
        }:
            raise SaveDataError("settled survival summary requires three zone temperatures")
        if daily.settled_day not in {
            state.calendar.current_day,
            state.calendar.current_day - 1,
        }:
            raise SaveDataError("survival summary must describe the current or previous day")

    management = state.building_management
    official_zones = {"inner_ring", "middle_ring", "outer_ring", "storage_outer"}
    if set(management.zone_slot_capacity) != official_zones:
        raise SaveDataError("building slot capacity must use the four official regions")
    if set(management.zone_slots_used) != official_zones:
        raise SaveDataError("building slot usage must use the four official regions")
    calculated_slots = {zone: 0 for zone in official_zones}
    for building_id, building in state.buildings.items():
        if building.building_id != building_id:
            raise SaveDataError("building_id must match its map key")
        if building.zone not in official_zones:
            raise SaveDataError(f"unsupported building zone: {building.zone}")
        calculated_slots[building.zone] += building.slot_size
    if management.zone_slots_used != calculated_slots:
        raise SaveDataError("building slot usage must match built buildings")
    if any(
        management.zone_slots_used[zone] > management.zone_slot_capacity[zone]
        for zone in official_zones
    ):
        raise SaveDataError("building slot usage cannot exceed capacity")
    if management.available_hunting_areas > management.total_hunting_areas:
        raise SaveDataError("available hunting areas cannot exceed total hunting areas")
    for resource_point_id, point in state.surface_resource_points.items():
        if point.resource_point_id != resource_point_id:
            raise SaveDataError("resource_point_id must match its map key")
        assigned = point.assigned_workers + point.assigned_engineers
        if assigned > point.staff_capacity:
            raise SaveDataError("surface resource point staff exceeds capacity")
        if point.production_remainder_numerator >= point.staff_capacity:
            raise SaveDataError("surface resource point remainder must be below capacity")
        if point.is_depleted != (point.remaining_amount == 0):
            raise SaveDataError("surface resource point depletion must match remaining amount")
        if point.is_depleted and assigned:
            raise SaveDataError("depleted surface resource points cannot retain staff")


def _validate_building_rule_invariants(
    state: GameState,
    rules: Any,
    survival_rules: Any | None,
    technology_rules: Any | None = None,
) -> None:
    if state.building_management.zone_slot_capacity != dict(rules.zone_slot_capacity):
        raise SaveDataError("building slot capacity must match building rules")
    if state.building_management.total_hunting_areas != len(
        rules.resource_anchors["hunting_area"]
    ):
        raise SaveDataError("hunting area count must match building rules")
    if state.building_management.forest_zones != len(
        rules.resource_anchors["forest_zone"]
    ):
        raise SaveDataError("forest zone count must match building rules")
    heated_building_count = sum(
        building.heated_today for building in state.buildings.values()
    )
    if state.building_management.heat_uses_today != heated_building_count:
        raise SaveDataError("daily heat uses must match heated buildings")
    if heated_building_count > rules.heat.daily_city_limit:
        raise SaveDataError("daily heat uses exceed the city limit")

    assigned = {
        "workers": 0,
        "engineers": 0,
        "children": 0,
        "medical_apprentices": 0,
        "engineering_apprentices": 0,
    }
    staff_fields = {
        "workers": "assigned_workers",
        "engineers": "assigned_engineers",
        "children": "assigned_children",
        "medical_apprentices": "assigned_medical_apprentices",
        "engineering_apprentices": "assigned_engineering_apprentices",
    }
    bound_ids: set[str] = set()
    expected_housing_capacity = 0
    expected_basic_residences = 0
    expected_storage_capacity = (
        survival_rules.resources.storage_capacity
        if survival_rules is not None
        else None
    )
    building_counts: dict[str, int] = {}
    for building in state.buildings.values():
        if not building.is_built:
            raise SaveDataError(
                "building registry cannot contain an unfinished building"
            )
        building_counts[building.building_type] = (
            building_counts.get(building.building_type, 0) + 1
        )
    for building_type, count in building_counts.items():
        rule = rules.buildings.get(building_type)
        if rule is None:
            continue
        if rule.max_count_source == "hunting_areas":
            maximum = state.building_management.available_hunting_areas
        elif rule.max_count_source == "forest_zones":
            maximum = state.building_management.forest_zones
        else:
            maximum = rule.max_buildings
        if maximum is not None and count > maximum:
            raise SaveDataError("building count exceeds its configured limit")
    expected_hunting_areas = 2 if building_counts.get("hunting_lodge", 0) else 1
    if state.building_management.available_hunting_areas != expected_hunting_areas:
        raise SaveDataError("available hunting areas must match hunting lodge progress")
    if building_counts.get("cemetery", 0) and building_counts.get("cold_pit", 0):
        raise SaveDataError("cemetery and cold pit are mutually exclusive")

    for building in state.buildings.values():
        rule = rules.buildings.get(building.building_type)
        if rule is None:
            raise SaveDataError(f"unknown building type: {building.building_type}")
        if building.zone not in rule.allowed_zones:
            raise SaveDataError("building zone does not match its catalog rule")
        if not set(rule.required_law_ids).issubset(state.laws.signed_law_ids):
            raise SaveDataError("built building is missing a required signed law")
        if not set(rule.required_tech_ids).issubset(
            state.technologies.researched_tech_ids
        ):
            raise SaveDataError("built building is missing a required technology")
        if building.slot_size != rule.slot_size or building.can_heat != rule.can_heat:
            raise SaveDataError("building derived fields do not match the catalog")
        if building.heated_today and not rule.can_heat:
            raise SaveDataError("building type cannot retain a heat marker")
        building_staff = 0
        for population_type, field_name in staff_fields.items():
            value = getattr(building, field_name)
            assigned[population_type] += value
            building_staff += value
            if value and population_type not in rule.allowed_staff_types:
                raise SaveDataError("building contains a disallowed staff type")
        if building_staff > rule.staff_capacity:
            raise SaveDataError("building staff exceeds catalog capacity")
        if rule.staff_capacity:
            if building.production_remainder_numerator >= rule.staff_capacity:
                raise SaveDataError("building production remainder must be below capacity")
        elif building.production_remainder_numerator:
            raise SaveDataError("unstaffed building cannot have a production remainder")
        if (
            building.production_multiplier_remainder_numerator
            >= building.production_multiplier_remainder_denominator
        ):
            raise SaveDataError("building production multiplier remainder must be proper")
        if rule.binding_kind is None:
            if building.bound_resource_id is not None:
                raise SaveDataError("building has an unsupported resource binding")
        else:
            if building.bound_resource_id not in rules.resource_anchors[rule.binding_kind]:
                raise SaveDataError("building resource binding does not match its catalog rule")
            assert building.bound_resource_id is not None
            if building.bound_resource_id in bound_ids:
                raise SaveDataError("resource bindings must be unique")
            bound_ids.add(building.bound_resource_id)
        expected_housing_capacity += rule.housing_capacity
        if expected_storage_capacity is not None:
            storage_add = rule.storage_capacity_add
            if (
                technology_rules is not None
                and building.building_type == "small_warehouse"
                and "tech_storage_expansion"
                in state.technologies.researched_tech_ids
            ):
                storage_add = 600
            expected_storage_capacity += storage_add
        if building.building_type == "basic_residence":
            expected_basic_residences += 1

    if state.housing.capacity != expected_housing_capacity:
        raise SaveDataError("housing capacity must match built residences")
    if state.housing.basic_residences != expected_basic_residences:
        raise SaveDataError("basic residence count must match built residences")
    if (
        expected_storage_capacity is not None
        and state.resources.storage_capacity != expected_storage_capacity
    ):
        raise SaveDataError("storage capacity must match survival and building rules")

    if set(state.surface_resource_points) != set(rules.surface_resource_points):
        raise SaveDataError("surface resource point map must match building rules")
    for resource_point_id, point in state.surface_resource_points.items():
        rule = rules.surface_resource_points[resource_point_id]
        if point.resource_type != rule.resource_type or point.staff_capacity != rule.staff_capacity:
            raise SaveDataError("surface resource point derived fields do not match rules")
        if point.remaining_amount > rule.total_amount:
            raise SaveDataError("surface resource point exceeds its configured reserve")
        assigned["workers"] += point.assigned_workers
        assigned["engineers"] += point.assigned_engineers

    if assigned["workers"] > state.population.workers:
        raise SaveDataError("assigned workers exceed the population pool")
    if assigned["engineers"] > state.population.engineers:
        raise SaveDataError("assigned engineers exceed the population pool")
    if assigned["medical_apprentices"] > state.population.medical_apprentices:
        raise SaveDataError("assigned medical apprentices exceed the population pool")
    if assigned["engineering_apprentices"] > state.population.engineering_apprentices:
        raise SaveDataError("assigned engineering apprentices exceed the population pool")
    assigned_child_roles = (
        assigned["children"]
        + assigned["medical_apprentices"]
        + assigned["engineering_apprentices"]
    )
    if assigned_child_roles > state.population.children:
        raise SaveDataError("assigned child roles exceed the child population pool")


def validate_game_state(
    state: GameState,
    building_rules: Any | None = None,
    survival_rules: Any | None = None,
    technology_rules: Any | None = None,
) -> None:
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
    if technology_rules is not None:
        _validate_technology_rule_invariants(state, technology_rules)
    if building_rules is not None:
        if survival_rules is None:
            raise SaveDataError(
                "survival rules are required for config-aware building validation"
            )
        _validate_building_rule_invariants(
            state,
            building_rules,
            survival_rules,
            technology_rules,
        )


def _validate_technology_rule_invariants(
    state: GameState, technology_rules: Any
) -> None:
    known = set(technology_rules.technologies)
    completed = set(state.technologies.researched_tech_ids)
    if completed - known:
        raise SaveDataError("state contains unknown researched technologies")
    for tech_id in completed:
        rule = technology_rules.technologies[tech_id]
        if not set(rule.prerequisite_tech_ids).issubset(completed):
            raise SaveDataError("researched technology is missing a prerequisite")
        tier_unlock = technology_rules.tier_unlock_tech_id(rule.tier)
        if tier_unlock is not None and tier_unlock not in completed:
            raise SaveDataError("researched technology tier is not unlocked")

    active = state.technologies.active_research_id
    if active is not None:
        if active not in known:
            raise SaveDataError("active research id is unknown")
        rule = technology_rules.technologies[active]
        if not set(rule.prerequisite_tech_ids).issubset(completed):
            raise SaveDataError("active research is missing a prerequisite")
        tier_unlock = technology_rules.tier_unlock_tech_id(rule.tier)
        if tier_unlock is not None and tier_unlock not in completed:
            raise SaveDataError("active research tier is not unlocked")
        required = (
            rule.research_days
            * technology_rules.research.progress_units_per_day
        )
        if state.technologies.research_required_units != required:
            raise SaveDataError(
                "active research duration does not match technology rules"
            )

    overload_rule = technology_rules.overload.levels.get(
        state.furnace.overload_level
    )
    if overload_rule is None:
        raise SaveDataError("state contains an unknown overload level")
    if (
        overload_rule.required_tech_id is not None
        and overload_rule.required_tech_id not in completed
    ):
        raise SaveDataError("selected overload level is not unlocked")
    if state.furnace.pressure_redline_warned != (
        state.furnace.pressure >= technology_rules.overload.redline_threshold
    ):
        raise SaveDataError("redline warning must match configured pressure threshold")
    daily = state.daily_survival
    daily_target_overload_rule = technology_rules.overload.levels.get(
        daily.target_overload_level
    )
    if daily_target_overload_rule is None:
        raise SaveDataError("daily survival contains an unknown target overload level")
    if (
        daily_target_overload_rule.required_tech_id is not None
        and daily_target_overload_rule.required_tech_id not in completed
    ):
        raise SaveDataError("daily target overload level is not unlocked")
    daily_overload_rule = technology_rules.overload.levels.get(
        daily.effective_overload_level
    )
    if daily_overload_rule is None:
        raise SaveDataError("daily survival contains an unknown overload level")
    if (
        daily_overload_rule.required_tech_id is not None
        and daily_overload_rule.required_tech_id not in completed
    ):
        raise SaveDataError("daily overload level is not unlocked")
    if daily.overload_coal_paid != daily_overload_rule.coal_cost:
        raise SaveDataError("daily overload payment does not match technology rules")
    if (
        daily.overload_temperature_bonus
        != daily_overload_rule.temperature_bonus
    ):
        raise SaveDataError(
            "daily overload temperature bonus does not match technology rules"
        )
