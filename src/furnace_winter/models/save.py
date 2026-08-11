from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field, fields
from typing import Any

from furnace_winter.models.randomness import RANDOM_ALGORITHM, RandomState
from furnace_winter.models.ending_selection import (
    canonical_report_body_text_ids,
    canonical_report_pending_text_ids,
    canonical_report_title_text_id,
)
from furnace_winter.models.serialization import to_primitive
from furnace_winter.models.state import (
    CURRENT_SAVE_DATA_VERSION,
    FINAL_DAY,
    OVERTIME_BUILDING_TYPES,
    BuildingManagementState,
    BuildingState,
    CalendarState,
    ColdExposureState,
    DailySurvivalState,
    EventRecord,
    EventFollowupRecord,
    EventFollowupSettlementRecord,
    EventResolutionRecord,
    EventState,
    EndingReportState,
    FinalFrostState,
    FinalResultState,
    FrostDayRecord,
    FurnaceState,
    GameState,
    HardFailType,
    HousingState,
    HungerState,
    LawState,
    MapState,
    MedicalState,
    OathOrderState,
    OldCityState,
    PopulationState,
    PromiseRecord,
    PromiseSettlementRecord,
    PromiseState,
    ResourceState,
    RouteFacilityState,
    RunState,
    SocialPolicyState,
    SurfaceResourcePointState,
    TechState,
    TerminationReason,
    TrustPanicState,
    ENDING_ADDITIONAL_POOL_TAGS,
    ENDING_BODY_POOL_TEXT_IDS,
    ENDING_HARD_FAIL_BODY_POOL_TEXT_IDS,
    ENDING_HARD_FAIL_REASON_TEXT_IDS,
    ENDING_INTERROGATION_POOL_BY_ENDING,
    ENDING_PLAYER_ENDED_BODY_TEXT_IDS,
    ENDING_REPORT_DEATH_RECORD_TEXT_ID,
    ENDING_REPORT_NARRATIVE_POOL_TEXT_IDS,
    ENDING_REPORT_ZERO_FROST_DEATHS_TEXT_ID,
    ENDING_TITLE_TEXT_IDS,
)


class SaveDataError(ValueError):
    pass


_FIXED_ARRIVAL_DAYS = {
    "arrival_day6": 6,
    "arrival_day19": 19,
    "arrival_day37": 37,
}
_PROMISE_ID_PATTERN = re.compile(r"^promise-([0-9]{4,})$")
_EVENT_FOLLOWUPS = {
    "game.medical_ration": ("severe_case_backlog", "medical_ration_prompt"),
    "game.memorial": ("bodies_under_snow", "memorial_prompt"),
}
_EVENT_PROMISES = {
    "empty_pot": ("food", "ordinary"),
    "raw_food_dispute": ("food", "ordinary"),
    "medical_beds_emergency": ("medical", "ordinary"),
    "severe_case_backlog": ("medical", "serious"),
    "bodies_under_snow": ("body", "ordinary"),
    "children_request": ("children", "ordinary"),
    "overtime_empty_post": ("labor", "serious"),
    "coal_bottom": ("coal", "ordinary"),
    "furnace_redline": ("furnace", "serious"),
    "cold_house_night": ("housing", "ordinary"),
    "trust_crack": ("trust", "serious"),
    "city_unrest": ("panic", "serious"),
}
_FINAL_SYSTEM_IDS = {
    "coal_and_core",
    "food",
    "housing_and_temperature",
    "medical_and_disease",
    "trust_and_panic",
    "population_and_death",
}
_FINAL_ENDING_IDS = {
    "high_victory",
    "standard_victory",
    "bitter_victory",
    "collapse_survival",
    "ember_survival",
    "hard_fail",
}
_EXTREME_CRISIS_CONDITION_IDS = {
    "furnace_off",
    "heating_shortfall",
    "mass_exposure_level_4",
    "mass_homeless_exposure",
    "medical_capacity_zero_with_critical",
    "untreated_critical_at_least_10",
    "food_shortage_population_at_least_60",
    "critical_building_shutdown",
    "overload_redline_continued",
}


def _expected_report_pending_text_ids_from_values(
    *,
    ending_id: str | None,
    hard_fail_type: str | None,
    run_state: RunState,
    major_tags: list[str],
    defining_tags: list[str],
    frost_deaths: int,
) -> list[str]:
    pending: set[str] = {ENDING_REPORT_DEATH_RECORD_TEXT_ID}
    if ending_id == "hard_fail":
        if hard_fail_type is not None:
            pending.add(
                ENDING_HARD_FAIL_BODY_POOL_TEXT_IDS[hard_fail_type]
            )
        pending.add("ending.hard_fail.closing_pool")
    else:
        pending.update(ENDING_REPORT_NARRATIVE_POOL_TEXT_IDS)
        if ending_id is not None:
            pending.add(ENDING_BODY_POOL_TEXT_IDS[ending_id])
            interrogation_id = ENDING_INTERROGATION_POOL_BY_ENDING.get(
                ending_id
            )
            if interrogation_id is not None:
                pending.add(interrogation_id)
        tags = set(major_tags) | set(defining_tags)
        for text_id, matching_tags in ENDING_ADDITIONAL_POOL_TAGS.items():
            if tags & matching_tags:
                pending.add(text_id)
    if run_state is RunState.ENDED:
        pending.add(ENDING_BODY_POOL_TEXT_IDS["player_ended"])
    if frost_deaths == 0:
        pending.add(ENDING_REPORT_ZERO_FROST_DEATHS_TEXT_ID)
    return sorted(pending)


def _expected_report_pending_text_ids(state: GameState) -> list[str]:
    final = state.final_result
    return _expected_report_pending_text_ids_from_values(
        ending_id=final.ending_id,
        hard_fail_type=(
            final.hard_fail_type.value
            if final.hard_fail_type is not None
            else None
        ),
        run_state=final.run_state,
        major_tags=final.major_tags,
        defining_tags=final.defining_tags,
        frost_deaths=state.final_frost.frost_deaths,
    )


def _promise_sequence(promise_id: str) -> int:
    match = _PROMISE_ID_PATTERN.fullmatch(promise_id)
    if match is None:
        raise SaveDataError("promise ids must use the canonical promise-0001 format")
    sequence = int(match.group(1))
    if sequence < 1 or f"promise-{sequence:04d}" != promise_id:
        raise SaveDataError("promise ids must use the canonical promise-0001 format")
    return sequence


def _event_instance_id(event_id: str, occurrence_index: int) -> str:
    return f"{event_id}#{occurrence_index:04d}"


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
        if version < 14:
            if "cold_exposure" in migrated:
                if migrated["cold_exposure"] != to_primitive(ColdExposureState()):
                    raise SaveDataError(
                        "pre-v14 save cannot contain non-default cold-exposure state"
                    )
                migrated.pop("cold_exposure")
            if isinstance(migrated.get("hunger"), Mapping):
                raw_hunger = dict(migrated["hunger"])
                if "none_population" in raw_hunger:
                    population = migrated.get("population")
                    alive = (
                        population.get("population_alive")
                        if isinstance(population, Mapping)
                        else None
                    )
                    expected_defaults = to_primitive(HungerState())
                    safe = (
                        isinstance(alive, int)
                        and not isinstance(alive, bool)
                        and raw_hunger.get("none_population") == alive
                        and all(
                            raw_hunger.get(name) == expected_defaults[name]
                            for name in expected_defaults
                            if name != "none_population"
                        )
                    )
                    if not safe:
                        raise SaveDataError(
                            "pre-v14 save cannot contain Patch 013 hunger values"
                        )
                    raw_hunger = {
                        "mild_population": 0,
                        "severe_population": 0,
                        "starving_population": 0,
                    }
                migrated["hunger"] = raw_hunger
            if isinstance(migrated.get("final_frost"), Mapping):
                raw_final_frost = dict(migrated["final_frost"])
                defaults = to_primitive(FinalFrostState())
                for name in (
                    "wood_supply_check_day",
                    "wood_supply_surface_exhausted",
                    "wood_supply_logging_camp_available",
                    "wood_supply_wood_stock",
                    "wood_supply_logging_cost",
                    "wood_supply_alternative_available",
                    "wood_supply_legacy_exempt",
                    "wood_supply_locked",
                    "legacy_hunger_history_unknown",
                    "legacy_hunger_record_days",
                    "frost_hunger_days",
                    "frost_unfed_person_days",
                    "frost_population_person_days",
                    "frost_peak_unfed_count",
                    "frost_peak_population_start",
                    "frost_hunger_deaths",
                ):
                    if name in raw_final_frost:
                        if raw_final_frost[name] != defaults[name]:
                            raise SaveDataError(
                                "pre-v14 save cannot contain Patch 013 wood-supply values"
                            )
                        raw_final_frost.pop(name)
                raw_daily_records = raw_final_frost.get("daily_records")
                if isinstance(raw_daily_records, Mapping):
                    cleaned_records: dict[str, Any] = {}
                    for day_key, raw_record in raw_daily_records.items():
                        if not isinstance(raw_record, Mapping):
                            cleaned_records[str(day_key)] = raw_record
                            continue
                        record = dict(raw_record)
                        if "unfed_population" in record:
                            if record["unfed_population"] != 0:
                                raise SaveDataError(
                                    "pre-v14 save cannot contain Patch 013 frost hunger values"
                                )
                            record.pop("unfed_population")
                        for name in (
                            "raw_hunger_deaths",
                            "hunger_death_overflow",
                        ):
                            if name in record:
                                if record[name] != 0:
                                    raise SaveDataError(
                                        "pre-v14 save cannot contain Patch 013 frost hunger values"
                                    )
                                record.pop(name)
                        cleaned_records[str(day_key)] = record
                    raw_final_frost["daily_records"] = cleaned_records
                migrated["final_frost"] = raw_final_frost
            if isinstance(migrated.get("final_result"), Mapping):
                raw_final_result = dict(migrated["final_result"])
                raw_report = raw_final_result.get("report")
                if isinstance(raw_report, Mapping):
                    report = dict(raw_report)
                    if "limiting_factor_ids" in report:
                        if report["limiting_factor_ids"] != []:
                            raise SaveDataError(
                                "pre-v14 save cannot contain Patch 013 report values"
                            )
                        report.pop("limiting_factor_ids")
                    raw_final_result["report"] = report
                    migrated["final_result"] = raw_final_result
        if version < 13 and "map" in migrated:
            if migrated["map"] != to_primitive(MapState()):
                raise SaveDataError(
                    "pre-v13 save cannot contain non-default map state"
                )
            migrated.pop("map")
        if version < 11 and "final_frost" in migrated:
            legacy_final_frost_default = to_primitive(FinalFrostState())
            for name in (
                "wood_supply_check_day",
                "wood_supply_surface_exhausted",
                "wood_supply_logging_camp_available",
                "wood_supply_wood_stock",
                "wood_supply_logging_cost",
                "wood_supply_alternative_available",
                "wood_supply_legacy_exempt",
                "wood_supply_locked",
                "legacy_hunger_history_unknown",
                "legacy_hunger_record_days",
                "frost_hunger_days",
                "frost_unfed_person_days",
                "frost_population_person_days",
                "frost_peak_unfed_count",
                "frost_peak_population_start",
                "frost_hunger_deaths",
            ):
                legacy_final_frost_default.pop(name)
            if migrated["final_frost"] != legacy_final_frost_default:
                raise SaveDataError(
                    "pre-v11 save cannot contain non-default final-frost state"
                )
            migrated.pop("final_frost")
        if version < 12 and isinstance(migrated.get("final_result"), Mapping):
            raw_final_result = dict(migrated["final_result"])
            patch_010_fields = set(_field_names(FinalResultState)) - set(
                _V11_FINAL_RESULT_FIELDS
            )
            older_fields = set(raw_final_result) - patch_010_fields
            if (
                patch_010_fields.issubset(raw_final_result)
                and frozenset(older_fields)
                in {
                    frozenset(_V10_FINAL_RESULT_FIELDS),
                    frozenset(_V11_FINAL_RESULT_FIELDS),
                }
            ):
                defaults = to_primitive(FinalResultState())
                for name in patch_010_fields:
                    expected = defaults[name]
                    if name == "report" and isinstance(expected, dict):
                        expected = dict(expected)
                        expected.pop("limiting_factor_ids", None)
                    if raw_final_result[name] != expected:
                        raise SaveDataError(
                            "pre-v12 save cannot contain Patch 010 final values"
                        )
                migrated["final_result"] = {
                    name: raw_final_result[name]
                    for name in raw_final_result
                    if name not in patch_010_fields
                }
        if version < 11 and isinstance(migrated.get("final_result"), Mapping):
            raw_final_result = dict(migrated["final_result"])
            if set(raw_final_result) == set(_V11_FINAL_RESULT_FIELDS):
                defaults = to_primitive(FinalResultState())
                for name in set(raw_final_result) - set(
                    _V10_FINAL_RESULT_FIELDS
                ):
                    if raw_final_result[name] != defaults[name]:
                        raise SaveDataError(
                            "pre-v11 save cannot contain Patch 009 final values"
                        )
                migrated["final_result"] = {
                    name: raw_final_result[name]
                    for name in _V10_FINAL_RESULT_FIELDS
                }
        if version < 11 and isinstance(migrated.get("medical"), Mapping):
            raw_medical = dict(migrated["medical"])
            if set(raw_medical) == set(_field_names(MedicalState)):
                if raw_medical["sick_treatment_progress"] != 0:
                    raise SaveDataError(
                        "pre-v11 save cannot contain sick treatment progress"
                    )
                migrated["medical"] = {
                    name: raw_medical[name] for name in _V10_MEDICAL_FIELDS
                }
        if version < 10 and "oath_order" in migrated:
            if migrated["oath_order"] != to_primitive(OathOrderState()):
                raise SaveDataError(
                    "pre-v10 save cannot contain non-default oath/order state"
                )
            migrated.pop("oath_order")
        if version < 10 and isinstance(migrated.get("old_city"), Mapping):
            raw_old_city = dict(migrated["old_city"])
            if set(raw_old_city) == set(_field_names(OldCityState)):
                defaults = to_primitive(OldCityState())
                for name in set(raw_old_city) - set(_V9_OLD_CITY_FIELDS):
                    if raw_old_city[name] != defaults[name]:
                        raise SaveDataError(
                            "pre-v10 save cannot contain Patch 008 old-city values"
                        )
                migrated["old_city"] = {
                    name: raw_old_city[name] for name in _V9_OLD_CITY_FIELDS
                }

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


_V13_GAME_STATE_FIELDS = tuple(
    name for name in _field_names(GameState) if name != "cold_exposure"
)
_V12_GAME_STATE_FIELDS = tuple(
    name for name in _V13_GAME_STATE_FIELDS if name != "map"
)
_V10_GAME_STATE_FIELDS = tuple(
    name for name in _V12_GAME_STATE_FIELDS if name != "final_frost"
)
_V9_GAME_STATE_FIELDS = tuple(
    name
    for name in _V12_GAME_STATE_FIELDS
    if name not in {"oath_order", "final_frost"}
)
_V10_FINAL_RESULT_FIELDS = (
    "is_finalized",
    "ending_id",
    "hard_fail_type",
    "ending_tags",
)
_V11_FINAL_RESULT_FIELDS = (
    *_V10_FINAL_RESULT_FIELDS,
    "system_scores",
    "total_score",
    "major_tags",
    "defining_tags",
)
_PATCH_013_FINAL_FROST_FIELDS = {
    "wood_supply_check_day",
    "wood_supply_surface_exhausted",
    "wood_supply_logging_camp_available",
    "wood_supply_wood_stock",
    "wood_supply_logging_cost",
    "wood_supply_alternative_available",
    "wood_supply_legacy_exempt",
    "wood_supply_locked",
    "legacy_hunger_history_unknown",
    "legacy_hunger_record_days",
    "frost_hunger_days",
    "frost_unfed_person_days",
    "frost_population_person_days",
    "frost_peak_unfed_count",
    "frost_peak_population_start",
    "frost_hunger_deaths",
}
_V13_FINAL_FROST_FIELDS = tuple(
    name
    for name in _field_names(FinalFrostState)
    if name not in _PATCH_013_FINAL_FROST_FIELDS
)
_PATCH_013_FROST_DAY_FIELDS = {
    "unfed_population",
    "raw_hunger_deaths",
    "hunger_death_overflow",
}
_V13_FROST_DAY_FIELDS = tuple(
    name
    for name in _field_names(FrostDayRecord)
    if name not in _PATCH_013_FROST_DAY_FIELDS
)
_V10_MEDICAL_FIELDS = tuple(
    name
    for name in _field_names(MedicalState)
    if name != "sick_treatment_progress"
)
_V9_OLD_CITY_FIELDS = (
    "is_unlocked",
    "active_stage_id",
    "trigger_day",
    "activation_pending",
)


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
_V8_EVENT_RECORD_FIELDS = tuple(
    name
    for name in _field_names(EventRecord)
    if name not in {"instance_id", "occurrence_index"}
)
_V8_EVENT_RESOLUTION_FIELDS = tuple(
    name
    for name in _field_names(EventResolutionRecord)
    if name not in {"instance_id", "occurrence_index"}
)
_V8_EVENT_FOLLOWUP_FIELDS = tuple(
    name
    for name in _field_names(EventFollowupRecord)
    if name != "instance_id"
)
_V8_EVENT_STATE_FIELDS = tuple(
    name
    for name in _field_names(EventState)
    if name
    not in {
        "consumed_followups",
        "fixed_arrival_pressure_days",
        "natural_death_overflow_candidates",
    }
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


def _optional_integer(
    value: Any,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None:
        return None
    return _integer(value, path, minimum=minimum, maximum=maximum)


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


def _integer_list(
    value: Any,
    path: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> list[int]:
    if not isinstance(value, list):
        raise SaveDataError(f"{path} must be an array")
    return [
        _integer(
            item,
            f"{path}[{index}]",
            minimum=minimum,
            maximum=maximum,
        )
        for index, item in enumerate(value)
    ]


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


def _day_list_map(value: Any, path: str) -> dict[str, list[int]]:
    if not isinstance(value, Mapping):
        raise SaveDataError(f"{path} must be an object")
    result: dict[str, list[int]] = {}
    for key, item in value.items():
        checked_key = _string(key, f"{path} key")
        assert isinstance(checked_key, str)
        result[checked_key] = _integer_list(
            item,
            f"{path}.{checked_key}",
            minimum=1,
            maximum=FINAL_DAY,
        )
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


def _decode_map(value: Any) -> MapState:
    data = _object(value, "map", _field_names(MapState))
    return MapState(
        map_key=str(_string(data["map_key"], "map.map_key")),
        selection_mode=str(
            _string(data["selection_mode"], "map.selection_mode")
        ),
        display_name_zh=str(
            _string(data["display_name_zh"], "map.display_name_zh")
        ),
        difficulty_zh=str(
            _string(data["difficulty_zh"], "map.difficulty_zh")
        ),
        small_coal_piles=_integer(
            data["small_coal_piles"],
            "map.small_coal_piles",
            minimum=1,
        ),
        small_wood_piles=_integer(
            data["small_wood_piles"],
            "map.small_wood_piles",
            minimum=1,
        ),
        small_steel_piles=_integer(
            data["small_steel_piles"],
            "map.small_steel_piles",
            minimum=1,
        ),
        initial_hunting_grounds=_integer(
            data["initial_hunting_grounds"],
            "map.initial_hunting_grounds",
            minimum=1,
        ),
        total_hunting_grounds=_integer(
            data["total_hunting_grounds"],
            "map.total_hunting_grounds",
            minimum=1,
        ),
        forest_zones=_integer(
            data["forest_zones"], "map.forest_zones", minimum=1
        ),
        large_coal_mine_points=_integer(
            data["large_coal_mine_points"],
            "map.large_coal_mine_points",
            minimum=1,
        ),
        large_steel_mine_points=_integer(
            data["large_steel_mine_points"],
            "map.large_steel_mine_points",
            minimum=1,
        ),
    )


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
    return HungerState(**{
        name: _integer(data[name], f"hunger.{name}", minimum=0)
        for name in _field_names(HungerState)
    })


def _decode_cold_exposure(value: Any) -> ColdExposureState:
    data = _object(value, "cold_exposure", _field_names(ColdExposureState))
    return ColdExposureState(
        **{
            name: _nonnegative_int_object(
                data[name], f"cold_exposure.{name}"
            )
            for name in _field_names(ColdExposureState)
        }
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
            instance_id=_string(
                item["instance_id"],
                f"events.active_events.{event_id}.instance_id",
            ),
            occurrence_index=_integer(
                item["occurrence_index"],
                f"events.active_events.{event_id}.occurrence_index",
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
                instance_id=_string(
                    item["instance_id"], f"{path}.instance_id"
                ),
                occurrence_index=_integer(
                    item["occurrence_index"],
                    f"{path}.occurrence_index",
                    minimum=1,
                ),
                promise_id=_string(
                    item["promise_id"], f"{path}.promise_id", optional=True
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
    raw_followups = data["pending_followups"]
    if not isinstance(raw_followups, Mapping):
        raise SaveDataError("events.pending_followups must be an object")
    pending_followups: dict[str, EventFollowupRecord] = {}
    for raw_command, raw_followup in raw_followups.items():
        command_name = _string(raw_command, "events.pending_followups key")
        assert isinstance(command_name, str)
        path = f"events.pending_followups.{command_name}"
        item = _object(raw_followup, path, _field_names(EventFollowupRecord))
        pending_followups[command_name] = EventFollowupRecord(
            instance_id=_string(item["instance_id"], f"{path}.instance_id"),
            event_id=_string(item["event_id"], f"{path}.event_id"),
            option_id=_string(item["option_id"], f"{path}.option_id"),
            command_name=_string(item["command_name"], f"{path}.command_name"),
            created_day=_integer(
                item["created_day"], f"{path}.created_day", minimum=1, maximum=FINAL_DAY
            ),
            occurrence_index=_integer(
                item["occurrence_index"], f"{path}.occurrence_index", minimum=1
            ),
        )
    raw_consumed_followups = data["consumed_followups"]
    if not isinstance(raw_consumed_followups, list):
        raise SaveDataError("events.consumed_followups must be an array")
    consumed_followups: list[EventFollowupSettlementRecord] = []
    for index, raw_followup in enumerate(raw_consumed_followups):
        path = f"events.consumed_followups[{index}]"
        item = _object(
            raw_followup,
            path,
            _field_names(EventFollowupSettlementRecord),
        )
        consumed_followups.append(
            EventFollowupSettlementRecord(
                instance_id=_string(item["instance_id"], f"{path}.instance_id"),
                event_id=_string(item["event_id"], f"{path}.event_id"),
                option_id=_string(item["option_id"], f"{path}.option_id"),
                command_name=_string(
                    item["command_name"], f"{path}.command_name"
                ),
                created_day=_integer(
                    item["created_day"],
                    f"{path}.created_day",
                    minimum=1,
                    maximum=FINAL_DAY,
                ),
                occurrence_index=_integer(
                    item["occurrence_index"],
                    f"{path}.occurrence_index",
                    minimum=1,
                ),
                settled_day=_integer(
                    item["settled_day"],
                    f"{path}.settled_day",
                    minimum=1,
                    maximum=FINAL_DAY,
                ),
                settled_command_sequence=_integer(
                    item["settled_command_sequence"],
                    f"{path}.settled_command_sequence",
                    minimum=1,
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
        fixed_arrival_pressure_days=_day_list_map(
            data["fixed_arrival_pressure_days"],
            "events.fixed_arrival_pressure_days",
        ),
        natural_death_overflow_candidates=_nonnegative_int_object(
            data["natural_death_overflow_candidates"],
            "events.natural_death_overflow_candidates",
        ),
        pending_followups=pending_followups,
        consumed_followups=consumed_followups,
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
        reference_population=_integer(
            data["reference_population"], "old_city.reference_population", minimum=0
        ),
        member_count=_integer(
            data["member_count"], "old_city.member_count", minimum=0
        ),
        low_threshold=_integer(
            data["low_threshold"], "old_city.low_threshold", minimum=0
        ),
        middle_threshold=_integer(
            data["middle_threshold"], "old_city.middle_threshold", minimum=0
        ),
        high_threshold=_integer(
            data["high_threshold"], "old_city.high_threshold", minimum=0
        ),
        countdown_day=_optional_integer(
            data["countdown_day"], "old_city.countdown_day", minimum=1
        ),
        resolved=_boolean(data["resolved"], "old_city.resolved"),
        result_id=_string(data["result_id"], "old_city.result_id", optional=True),
        last_daily_trend=_integer(
            data["last_daily_trend"], "old_city.last_daily_trend"
        ),
        recent_major_death_days=_integer_list(
            data["recent_major_death_days"],
            "old_city.recent_major_death_days",
            minimum=1,
            maximum=FINAL_DAY,
        ),
        stage_events_seen=_string_list(
            data["stage_events_seen"], "old_city.stage_events_seen"
        ),
        pending_event_id=_string(
            data["pending_event_id"], "old_city.pending_event_id", optional=True
        ),
        hidden_growth_days_remaining=_integer(
            data["hidden_growth_days_remaining"],
            "old_city.hidden_growth_days_remaining",
            minimum=0,
        ),
        promise_active=_boolean(
            data["promise_active"], "old_city.promise_active"
        ),
        promise_created_day=_optional_integer(
            data["promise_created_day"], "old_city.promise_created_day", minimum=1
        ),
        promise_deadline_day=_optional_integer(
            data["promise_deadline_day"], "old_city.promise_deadline_day", minimum=1
        ),
        promise_target_count=_optional_integer(
            data["promise_target_count"], "old_city.promise_target_count", minimum=0
        ),
        promise_settled=_boolean(
            data["promise_settled"], "old_city.promise_settled"
        ),
        promise_outcome=_string(
            data["promise_outcome"], "old_city.promise_outcome", optional=True
        ),
        promise_settled_day=_optional_integer(
            data["promise_settled_day"],
            "old_city.promise_settled_day",
            minimum=1,
        ),
        settlement_day=_optional_integer(
            data["settlement_day"], "old_city.settlement_day", minimum=1
        ),
        settlement_member_count=_integer(
            data["settlement_member_count"],
            "old_city.settlement_member_count",
            minimum=0,
        ),
        theoretical_departures=_integer(
            data["theoretical_departures"],
            "old_city.theoretical_departures",
            minimum=0,
        ),
        actual_departures=_integer(
            data["actual_departures"],
            "old_city.actual_departures",
            minimum=0,
        ),
        protected_jobs=_nonnegative_int_object(
            data["protected_jobs"], "old_city.protected_jobs"
        ),
        protected_engineers=_integer(
            data["protected_engineers"],
            "old_city.protected_engineers",
            minimum=0,
        ),
        reduction_reason=_string(
            data["reduction_reason"],
            "old_city.reduction_reason",
            optional=True,
        ),
        settlement_resource_losses=_nonnegative_int_object(
            data["settlement_resource_losses"],
            "old_city.settlement_resource_losses",
        ),
    )


def _decode_route_facility(value: Any, path: str) -> RouteFacilityState:
    data = _object(value, path, _field_names(RouteFacilityState))
    return RouteFacilityState(
        enabled=_boolean(data["enabled"], f"{path}.enabled"),
        visible=_boolean(data["visible"], f"{path}.visible"),
        assigned_workers=_integer(
            data["assigned_workers"], f"{path}.assigned_workers", minimum=0
        ),
        assigned_engineers=_integer(
            data["assigned_engineers"], f"{path}.assigned_engineers", minimum=0
        ),
        is_running=_boolean(data["is_running"], f"{path}.is_running"),
    )


def _decode_oath_order(value: Any) -> OathOrderState:
    data = _object(value, "oath_order", _field_names(OathOrderState))
    return OathOrderState(
        page_unlocked=_boolean(data["page_unlocked"], "oath_order.page_unlocked"),
        selected_route=_string(
            data["selected_route"], "oath_order.selected_route", optional=True
        ),
        signed_law_ids=_string_list(
            data["signed_law_ids"], "oath_order.signed_law_ids"
        ),
        law_signed_days=_nonnegative_int_object(
            data["law_signed_days"], "oath_order.law_signed_days"
        ),
        next_law_day=_integer(
            data["next_law_day"], "oath_order.next_law_day", minimum=1
        ),
        oath_hall=_decode_route_facility(
            data["oath_hall"], "oath_order.oath_hall"
        ),
        patrol_office=_decode_route_facility(
            data["patrol_office"], "oath_order.patrol_office"
        ),
        action_next_available_day=_nonnegative_int_object(
            data["action_next_available_day"],
            "oath_order.action_next_available_day",
        ),
        action_last_used_day=_nonnegative_int_object(
            data["action_last_used_day"], "oath_order.action_last_used_day"
        ),
        final_oath_active=_boolean(
            data["final_oath_active"], "oath_order.final_oath_active"
        ),
        highest_order_active=_boolean(
            data["highest_order_active"], "oath_order.highest_order_active"
        ),
        death_panic_aftershock_halved_day=_optional_integer(
            data["death_panic_aftershock_halved_day"],
            "oath_order.death_panic_aftershock_halved_day",
            minimum=1,
        ),
        ending_tag_candidates=_string_list(
            data["ending_tag_candidates"], "oath_order.ending_tag_candidates"
        ),
    )


def _decode_ending_report(value: Any) -> EndingReportState:
    data = _object(value, "final_result.report", _field_names(EndingReportState))
    return EndingReportState(
        is_generated=_boolean(
            data["is_generated"], "final_result.report.is_generated"
        ),
        generated_day=_optional_integer(
            data["generated_day"],
            "final_result.report.generated_day",
            minimum=1,
            maximum=FINAL_DAY,
        ),
        ending_state=_string(
            data["ending_state"],
            "final_result.report.ending_state",
            optional=True,
        ),
        display_result_id=_string(
            data["display_result_id"],
            "final_result.report.display_result_id",
            optional=True,
        ),
        title_text_id=_string(
            data["title_text_id"],
            "final_result.report.title_text_id",
            optional=True,
        ),
        body_text_ids=_string_list(
            data["body_text_ids"], "final_result.report.body_text_ids"
        ),
        pending_text_ids=_string_list(
            data["pending_text_ids"], "final_result.report.pending_text_ids"
        ),
        hidden_achievement_ids=_string_list(
            data["hidden_achievement_ids"],
            "final_result.report.hidden_achievement_ids",
        ),
        limiting_factor_ids=_string_list(
            data["limiting_factor_ids"],
            "final_result.report.limiting_factor_ids",
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
    run_state_value = _string(data["run_state"], "final_result.run_state")
    termination_reason_value = _string(
        data["termination_reason"],
        "final_result.termination_reason",
        optional=True,
    )
    try:
        run_state = RunState(run_state_value)
        termination_reason = (
            None
            if termination_reason_value is None
            else TerminationReason(termination_reason_value)
        )
    except ValueError as exc:
        raise SaveDataError("unsupported final-result run lifecycle") from exc
    return FinalResultState(
        is_finalized=_boolean(data["is_finalized"], "final_result.is_finalized"),
        ending_id=_string(data["ending_id"], "final_result.ending_id", optional=True),
        hard_fail_type=hard_fail_type,
        ending_tags=_string_list(data["ending_tags"], "final_result.ending_tags"),
        system_scores=_nonnegative_int_object(
            data["system_scores"], "final_result.system_scores"
        ),
        total_score=_optional_integer(
            data["total_score"], "final_result.total_score", minimum=0
        ),
        major_tags=_string_list(data["major_tags"], "final_result.major_tags"),
        defining_tags=_string_list(
            data["defining_tags"], "final_result.defining_tags"
        ),
        run_state=run_state,
        termination_reason=termination_reason,
        termination_day=_optional_integer(
            data["termination_day"],
            "final_result.termination_day",
            minimum=1,
            maximum=FINAL_DAY,
        ),
        termination_command_sequence=_optional_integer(
            data["termination_command_sequence"],
            "final_result.termination_command_sequence",
            minimum=1,
        ),
        report=_decode_ending_report(data["report"]),
    )


def _decode_frost_day_record(value: Any, path: str) -> FrostDayRecord:
    data = _object(value, path, _field_names(FrostDayRecord))
    boolean_fields = {
        "furnace_off",
        "heating_shortfall",
        "coal_shortage",
        "furnace_underheated",
        "overload_used",
        "overload_redline",
        "core_near_collapse",
        "critical_building_frozen",
        "cold_houses_day",
        "mass_cold_exposure_day",
        "food_shortage",
        "starvation",
        "medical_overflow",
        "medical_collapse",
        "hospital_shutdown",
        "disease_spike",
        "mass_death",
        "trust_crisis",
        "panic_crisis",
    }
    integer_fields = set(_field_names(FrostDayRecord)) - boolean_fields - {
        "display_label",
        "extreme_crisis_conditions",
    }
    values: dict[str, Any] = {
        name: _boolean(data[name], f"{path}.{name}") for name in boolean_fields
    }
    for name in integer_fields:
        minimum = None if name == "real_temperature" else 0
        values[name] = _integer(data[name], f"{path}.{name}", minimum=minimum)
    values["display_label"] = _string(
        data["display_label"], f"{path}.display_label"
    )
    values["extreme_crisis_conditions"] = _string_list(
        data["extreme_crisis_conditions"],
        f"{path}.extreme_crisis_conditions",
    )
    return FrostDayRecord(**values)


def _decode_final_frost(value: Any) -> FinalFrostState:
    data = _object(value, "final_frost", _field_names(FinalFrostState))
    if not isinstance(data["daily_records"], Mapping):
        raise SaveDataError("final_frost.daily_records must be an object")
    records_raw = dict(data["daily_records"])
    records: dict[str, FrostDayRecord] = {}
    for key, item in records_raw.items():
        if not isinstance(key, str) or not key.isdigit() or str(int(key)) != key:
            raise SaveDataError("final_frost.daily_records keys must be canonical days")
        records[key] = _decode_frost_day_record(
            item, f"final_frost.daily_records.{key}"
        )
    return FinalFrostState(
        entered=_boolean(data["entered"], "final_frost.entered"),
        baseline_day=_optional_integer(
            data["baseline_day"], "final_frost.baseline_day", minimum=1
        ),
        baseline_alive_population=_integer(
            data["baseline_alive_population"],
            "final_frost.baseline_alive_population",
            minimum=0,
        ),
        baseline_healthy_population=_integer(
            data["baseline_healthy_population"],
            "final_frost.baseline_healthy_population",
            minimum=0,
        ),
        baseline_sick_population=_integer(
            data["baseline_sick_population"],
            "final_frost.baseline_sick_population",
            minimum=0,
        ),
        baseline_critical_population=_integer(
            data["baseline_critical_population"],
            "final_frost.baseline_critical_population",
            minimum=0,
        ),
        baseline_disabled_population=_integer(
            data["baseline_disabled_population"],
            "final_frost.baseline_disabled_population",
            minimum=0,
        ),
        baseline_workable_population=_integer(
            data["baseline_workable_population"],
            "final_frost.baseline_workable_population",
            minimum=0,
        ),
        prepared_item_count=_integer(
            data["prepared_item_count"],
            "final_frost.prepared_item_count",
            minimum=0,
        ),
        unprepared_item_count=_integer(
            data["unprepared_item_count"],
            "final_frost.unprepared_item_count",
            minimum=0,
        ),
        preparation_tags=_string_list(
            data["preparation_tags"], "final_frost.preparation_tags"
        ),
        wood_supply_check_day=_optional_integer(
            data["wood_supply_check_day"],
            "final_frost.wood_supply_check_day",
            minimum=1,
        ),
        wood_supply_surface_exhausted=_boolean(
            data["wood_supply_surface_exhausted"],
            "final_frost.wood_supply_surface_exhausted",
        ),
        wood_supply_logging_camp_available=_boolean(
            data["wood_supply_logging_camp_available"],
            "final_frost.wood_supply_logging_camp_available",
        ),
        wood_supply_wood_stock=_integer(
            data["wood_supply_wood_stock"],
            "final_frost.wood_supply_wood_stock",
            minimum=0,
        ),
        wood_supply_logging_cost=_integer(
            data["wood_supply_logging_cost"],
            "final_frost.wood_supply_logging_cost",
            minimum=0,
        ),
        wood_supply_alternative_available=_boolean(
            data["wood_supply_alternative_available"],
            "final_frost.wood_supply_alternative_available",
        ),
        wood_supply_legacy_exempt=_boolean(
            data["wood_supply_legacy_exempt"],
            "final_frost.wood_supply_legacy_exempt",
        ),
        wood_supply_locked=_boolean(
            data["wood_supply_locked"], "final_frost.wood_supply_locked"
        ),
        legacy_hunger_history_unknown=_boolean(
            data["legacy_hunger_history_unknown"],
            "final_frost.legacy_hunger_history_unknown",
        ),
        legacy_hunger_record_days=_integer_list(
            data["legacy_hunger_record_days"],
            "final_frost.legacy_hunger_record_days",
            minimum=49,
            maximum=55,
        ),
        pending_extreme_crisis_conditions=_string_list(
            data["pending_extreme_crisis_conditions"],
            "final_frost.pending_extreme_crisis_conditions",
        ),
        daily_records=records,
        frost_deaths=_integer(
            data["frost_deaths"], "final_frost.frost_deaths", minimum=0
        ),
        frost_hunger_days=_integer(
            data["frost_hunger_days"],
            "final_frost.frost_hunger_days",
            minimum=0,
        ),
        frost_unfed_person_days=_integer(
            data["frost_unfed_person_days"],
            "final_frost.frost_unfed_person_days",
            minimum=0,
        ),
        frost_population_person_days=_integer(
            data["frost_population_person_days"],
            "final_frost.frost_population_person_days",
            minimum=0,
        ),
        frost_peak_unfed_count=_integer(
            data["frost_peak_unfed_count"],
            "final_frost.frost_peak_unfed_count",
            minimum=0,
        ),
        frost_peak_population_start=_integer(
            data["frost_peak_population_start"],
            "final_frost.frost_peak_population_start",
            minimum=0,
        ),
        frost_hunger_deaths=_integer(
            data["frost_hunger_deaths"],
            "final_frost.frost_hunger_deaths",
            minimum=0,
        ),
        final_score_day=_optional_integer(
            data["final_score_day"], "final_frost.final_score_day", minimum=1
        ),
    )


def decode_game_state(
    document: Mapping[str, Any],
    migrations: SaveMigrationRegistry | None = None,
) -> GameState:
    return _decode_game_state(
        document, migrations, strict_event_timeline=True
    )


def _decode_game_state(
    document: Mapping[str, Any],
    migrations: SaveMigrationRegistry | None,
    *,
    strict_event_timeline: bool,
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
        migrations.register(8, _migrate_v8_to_v9)
        migrations.register(9, _migrate_v9_to_v10)
        migrations.register(10, _migrate_v10_to_v11)
        migrations.register(11, _migrate_v11_to_v12)
        migrations.register(12, _migrate_v12_to_v13)
        migrations.register(13, _migrate_v13_to_v14)
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
            cold_exposure=_decode_cold_exposure(data["cold_exposure"]),
            daily_survival=_decode_daily_survival(data["daily_survival"]),
            trust_panic=_decode_trust_panic(data["trust_panic"]),
            furnace=_decode_furnace(data["furnace"]),
            map=_decode_map(data["map"]),
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
            oath_order=_decode_oath_order(data["oath_order"]),
            final_frost=_decode_final_frost(data["final_frost"]),
            final_result=_decode_final_result(data["final_result"]),
        )
        _validate_state_invariants(
            state, strict_event_timeline=strict_event_timeline
        )
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
    legacy = _object(source, "$", set(_V9_GAME_STATE_FIELDS) - v2_only_fields)
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
        set(_V9_GAME_STATE_FIELDS)
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
        set(_V9_GAME_STATE_FIELDS) - {"surface_resource_points", "social_policy", "medical"},
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
        set(_V9_GAME_STATE_FIELDS) - {"social_policy", "medical"},
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
    legacy = _object(document, "$", _V9_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    calendar = _object(
        migrated["calendar"], "calendar", _field_names(CalendarState)
    )
    current_day = _integer(
        calendar["current_day"], "calendar.current_day", minimum=1, maximum=FINAL_DAY
    )
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
        if current_day > _FIXED_ARRIVAL_DAYS["arrival_day6"]:
            raise SaveDataError(
                "v7 saves after day 6 cannot reconstruct mandatory fixed arrivals"
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
            "pending_followups": {},
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
        event_fields = (
            _field_names(EventState)
            if set(raw_events) == set(_field_names(EventState))
            else _V8_EVENT_STATE_FIELDS
        )
        migrated["events"] = _object(raw_events, "events", event_fields)

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
        completed_ids = _string_list(
            promises["completed_promise_ids"],
            "promises.completed_promise_ids",
        )
        failed_ids = _string_list(
            promises["failed_promise_ids"], "promises.failed_promise_ids"
        )
        if completed_ids or failed_ids:
            raise SaveDataError(
                "v7 settled promises cannot be migrated without source and settlement history"
            )
        migrated["promises"] = {
            "active_promises": {},
            "completed_promise_ids": completed_ids,
            "failed_promise_ids": failed_ids,
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
            raw_old_city, "old_city", _V9_OLD_CITY_FIELDS
        )
    migrated["save_data_version"] = 8
    return migrated


def _migrate_v8_to_v9(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _V9_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    raw_events = migrated["events"]
    if not isinstance(raw_events, Mapping):
        raise SaveDataError("events must be an object")
    raw_events = dict(raw_events)
    raw_events.pop("consumed_followups", None)
    raw_events.pop("fixed_arrival_pressure_days", None)
    raw_events.pop("natural_death_overflow_candidates", None)
    if set(raw_events) == set(_field_names(EventState)):
        migrated["events"] = _object(
            raw_events, "events", _field_names(EventState)
        )
        migrated["save_data_version"] = 9
        return migrated

    events = _object(raw_events, "events", _V8_EVENT_STATE_FIELDS)
    occurrence_counts = _nonnegative_int_object(
        events["occurrence_counts"], "events.occurrence_counts"
    )

    raw_active = events["active_events"]
    if not isinstance(raw_active, Mapping):
        raise SaveDataError("events.active_events must be an object")
    active_events: dict[str, Any] = {}
    used_indices: dict[str, set[int]] = {}
    for raw_event_id, raw_event in raw_active.items():
        event_id = _string(raw_event_id, "events.active_events key")
        assert isinstance(event_id, str)
        item = _object(
            raw_event,
            f"events.active_events.{event_id}",
            _V8_EVENT_RECORD_FIELDS,
        )
        occurrence_index = occurrence_counts.get(event_id, 0)
        if occurrence_index < 1:
            raise SaveDataError(
                "v8 active event lacks a reconstructable occurrence index"
            )
        used_indices.setdefault(event_id, set()).add(occurrence_index)
        active_events[event_id] = {
            **item,
            "instance_id": _event_instance_id(event_id, occurrence_index),
            "occurrence_index": occurrence_index,
        }

    raw_history = events["resolution_history"]
    if not isinstance(raw_history, list):
        raise SaveDataError("events.resolution_history must be an array")
    resolution_history = [
        _object(
            raw_record,
            f"events.resolution_history[{index}]",
            _V8_EVENT_RESOLUTION_FIELDS,
        )
        for index, raw_record in enumerate(raw_history)
    ]

    raw_pending = events["pending_followups"]
    if not isinstance(raw_pending, Mapping):
        raise SaveDataError("events.pending_followups must be an object")
    pending_followups: dict[str, Any] = {}
    history_indices: dict[int, int] = {}
    for raw_command, raw_followup in raw_pending.items():
        command_name = _string(raw_command, "events.pending_followups key")
        assert isinstance(command_name, str)
        path = f"events.pending_followups.{command_name}"
        item = _object(raw_followup, path, _V8_EVENT_FOLLOWUP_FIELDS)
        event_id = _string(item["event_id"], f"{path}.event_id")
        option_id = _string(item["option_id"], f"{path}.option_id")
        created_day = _integer(
            item["created_day"],
            f"{path}.created_day",
            minimum=1,
            maximum=FINAL_DAY,
        )
        occurrence_index = _integer(
            item["occurrence_index"],
            f"{path}.occurrence_index",
            minimum=1,
        )
        assert isinstance(event_id, str) and isinstance(option_id, str)
        if occurrence_index > occurrence_counts.get(event_id, 0):
            raise SaveDataError(
                "v8 event followup occurrence cannot be reconstructed"
            )
        matches = [
            index
            for index, history in enumerate(resolution_history)
            if history["event_id"] == event_id
            and history["option_id"] == option_id
            and history["resolved_day"] == created_day
        ]
        if len(matches) != 1 or matches[0] in history_indices:
            raise SaveDataError(
                "v8 event followup lacks one reconstructable source instance"
            )
        if occurrence_index in used_indices.setdefault(event_id, set()):
            raise SaveDataError("v8 event occurrence identity is ambiguous")
        history_indices[matches[0]] = occurrence_index
        used_indices[event_id].add(occurrence_index)
        pending_followups[command_name] = {
            **item,
            "instance_id": _event_instance_id(event_id, occurrence_index),
        }

    for index, history in enumerate(resolution_history):
        source = (history["event_id"], history["option_id"])
        if source in set(_EVENT_FOLLOWUPS.values()) and index not in history_indices:
            raise SaveDataError(
                "v8 consumed event followup cannot be distinguished from a deleted marker"
            )

    next_indices: dict[str, list[int]] = {}
    for event_id, count in occurrence_counts.items():
        next_indices[event_id] = [
            index
            for index in range(1, count + 1)
            if index not in used_indices.get(event_id, set())
        ]
    migrated_history: list[dict[str, Any]] = []
    for index, history in enumerate(resolution_history):
        event_id = _string(
            history["event_id"],
            f"events.resolution_history[{index}].event_id",
        )
        assert isinstance(event_id, str)
        occurrence_index = history_indices.get(index)
        if occurrence_index is None:
            available = next_indices.get(event_id, [])
            if not available:
                raise SaveDataError(
                    "v8 event history occurrence cannot be reconstructed"
                )
            occurrence_index = available.pop(0)
        migrated_history.append(
            {
                **history,
                "instance_id": _event_instance_id(
                    event_id, occurrence_index
                ),
                "occurrence_index": occurrence_index,
            }
        )

    migrated["events"] = {
        **events,
        "active_events": active_events,
        "resolution_history": migrated_history,
        "pending_followups": pending_followups,
        "consumed_followups": [],
    }
    migrated["save_data_version"] = 9
    return migrated


def _migrate_v9_to_v10(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _V9_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    old_city = _object(
        migrated["old_city"], "old_city", _V9_OLD_CITY_FIELDS
    )
    calendar = _object(
        migrated["calendar"], "calendar", _field_names(CalendarState)
    )
    current_day = _integer(
        calendar["current_day"],
        "calendar.current_day",
        minimum=1,
        maximum=FINAL_DAY,
    )
    if old_city["is_unlocked"]:
        raise SaveDataError(
            "v9 unlocked old city cannot reconstruct the Patch 008 lifecycle"
        )
    if current_day > old_city["trigger_day"]:
        raise SaveDataError(
            "v9 save after day 24 cannot reconstruct the Patch 008 lifecycle"
        )
    migrated["old_city"] = {
        **old_city,
        "reference_population": 0,
        "member_count": 0,
        "low_threshold": 0,
        "middle_threshold": 0,
        "high_threshold": 0,
        "countdown_day": None,
        "resolved": False,
        "result_id": None,
        "last_daily_trend": 0,
        "recent_major_death_days": [],
        "stage_events_seen": [],
        "pending_event_id": None,
        "hidden_growth_days_remaining": 0,
        "promise_active": False,
        "promise_created_day": None,
        "promise_deadline_day": None,
        "promise_target_count": None,
        "promise_settled": False,
        "promise_outcome": None,
        "promise_settled_day": None,
        "settlement_day": None,
        "settlement_member_count": 0,
        "theoretical_departures": 0,
        "actual_departures": 0,
        "protected_jobs": {},
        "protected_engineers": 0,
        "reduction_reason": None,
        "settlement_resource_losses": {},
    }
    empty_facility = {
        "enabled": False,
        "visible": False,
        "assigned_workers": 0,
        "assigned_engineers": 0,
        "is_running": False,
    }
    migrated["oath_order"] = {
        "page_unlocked": False,
        "selected_route": None,
        "signed_law_ids": [],
        "law_signed_days": {},
        "next_law_day": 1,
        "oath_hall": deepcopy(empty_facility),
        "patrol_office": deepcopy(empty_facility),
        "action_next_available_day": {},
        "action_last_used_day": {},
        "final_oath_active": False,
        "highest_order_active": False,
        "death_panic_aftershock_halved_day": None,
        "ending_tag_candidates": [],
    }
    migrated["save_data_version"] = 10
    return migrated


def _migrate_v10_to_v11(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _V10_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    calendar = _object(
        migrated["calendar"], "calendar", _field_names(CalendarState)
    )
    current_day = _integer(
        calendar["current_day"],
        "calendar.current_day",
        minimum=1,
        maximum=FINAL_DAY,
    )
    daily = _object(
        migrated["daily_survival"],
        "daily_survival",
        _field_names(DailySurvivalState),
    )
    settled_day = _optional_integer(
        daily["settled_day"], "daily_survival.settled_day", minimum=1
    )
    if current_day >= 49 or (settled_day is not None and settled_day >= 49):
        raise SaveDataError(
            "v10 save at or after day 49 cannot reconstruct Patch 009 frost history"
        )
    if not isinstance(migrated["events"], Mapping):
        raise SaveDataError("events must be an object")
    legacy_events = dict(migrated["events"])
    arrival_choices = _string_map(
        legacy_events["fixed_arrival_choices"],
        "events.fixed_arrival_choices",
    )
    legal_settled_day = max(current_day - 1, settled_day or 0)
    for event_id, arrival_day in _FIXED_ARRIVAL_DAYS.items():
        if (
            arrival_choices.get(event_id) not in {None, "reject"}
            and legal_settled_day >= arrival_day
        ):
            raise SaveDataError(
                "v10 accepted arrival pressure history cannot be reconstructed"
            )
    raw_population = dict(migrated["population"])
    raw_population.pop("population_total_ever", None)
    population = dict(
        _object(
            raw_population,
            "population",
            tuple(
                name
                for name in _field_names(PopulationState)
                if name != "population_total_ever"
            ),
        )
    )
    old_city = _object(
        migrated["old_city"], "old_city", _field_names(OldCityState)
    )
    population_total = _integer(
        population["population_total"],
        "population.population_total",
        minimum=0,
    )
    actual_departures = _integer(
        old_city["actual_departures"],
        "old_city.actual_departures",
        minimum=0,
    )
    migrated["population"] = {
        **population,
        "population_total_ever": population_total + actual_departures,
    }
    events = dict(migrated["events"])
    events.pop("fixed_arrival_pressure_days", None)
    events.pop("natural_death_overflow_candidates", None)
    events["fixed_arrival_pressure_days"] = {}
    events["natural_death_overflow_candidates"] = {}
    migrated["events"] = events
    medical = _object(
        migrated["medical"], "medical", _V10_MEDICAL_FIELDS
    )
    migrated["medical"] = {**medical, "sick_treatment_progress": 0}
    final_result = _object(
        migrated["final_result"],
        "final_result",
        _V10_FINAL_RESULT_FIELDS,
    )
    migrated["final_result"] = {
        **final_result,
        "system_scores": {},
        "total_score": None,
        "major_tags": [],
        "defining_tags": [],
    }
    current_frost_default = to_primitive(FinalFrostState())
    migrated["final_frost"] = {
        name: current_frost_default[name]
        for name in _V13_FINAL_FROST_FIELDS
    }
    migrated["save_data_version"] = 11
    return migrated


def _migrate_v11_to_v12(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _V12_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    final_result = dict(_object(
        migrated["final_result"],
        "final_result",
        _V11_FINAL_RESULT_FIELDS,
    ))
    is_finalized = _boolean(
        final_result["is_finalized"], "final_result.is_finalized"
    )
    hard_fail_type = _string(
        final_result["hard_fail_type"],
        "final_result.hard_fail_type",
        optional=True,
    )
    if hard_fail_type is not None:
        if hard_fail_type not in ENDING_HARD_FAIL_REASON_TEXT_IDS:
            raise SaveDataError("unsupported hard_fail_type in v11 save")
        final_result["is_finalized"] = True
        final_result["ending_id"] = "hard_fail"
        final_result["ending_tags"] = ["hard_fail", hard_fail_type]
        final_result["system_scores"] = {}
        final_result["total_score"] = None
        final_result["major_tags"] = []
        final_result["defining_tags"] = []
        is_finalized = True

    report = to_primitive(EndingReportState())
    if is_finalized:
        calendar = _object(
            migrated["calendar"], "calendar", _field_names(CalendarState)
        )
        generated_day = _integer(
            calendar["current_day"],
            "calendar.current_day",
            minimum=1,
            maximum=FINAL_DAY,
        )
        ending_id = _string(
            final_result["ending_id"],
            "final_result.ending_id",
        )
        assert ending_id is not None
        if ending_id not in ENDING_TITLE_TEXT_IDS:
            raise SaveDataError("v11 final result has an unsupported ending id")
        major_tags = _string_list(
            final_result["major_tags"], "final_result.major_tags"
        )
        defining_tags = _string_list(
            final_result["defining_tags"], "final_result.defining_tags"
        )
        frost = _object(
            migrated["final_frost"],
            "final_frost",
            _V13_FINAL_FROST_FIELDS,
        )
        frost_deaths = _integer(
            frost["frost_deaths"],
            "final_frost.frost_deaths",
            minimum=0,
        )
        events = _object(
            migrated["events"], "events", _field_names(EventState)
        )
        hidden_achievements = sorted(
            set(
                _string_list(
                    events["hidden_achievements_unlocked"],
                    "events.hidden_achievements_unlocked",
                )
            )
        )
        report = {
            "is_generated": True,
            "generated_day": generated_day,
            "ending_state": ending_id,
            "display_result_id": ending_id,
            "title_text_id": ENDING_TITLE_TEXT_IDS[ending_id],
            "body_text_ids": (
                [ENDING_HARD_FAIL_REASON_TEXT_IDS[hard_fail_type]]
                if hard_fail_type is not None
                else []
            ),
            "pending_text_ids": _expected_report_pending_text_ids_from_values(
                ending_id=ending_id,
                hard_fail_type=hard_fail_type,
                run_state=RunState.ACTIVE,
                major_tags=major_tags,
                defining_tags=defining_tags,
                frost_deaths=frost_deaths,
            ),
            "hidden_achievement_ids": hidden_achievements,
        }
    migrated["final_result"] = {
        **final_result,
        "run_state": RunState.ACTIVE.value,
        "termination_reason": None,
        "termination_day": None,
        "termination_command_sequence": None,
        "report": report,
    }
    migrated["save_data_version"] = 12
    return migrated


def _migrate_v12_to_v13(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _V12_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    migrated["map"] = to_primitive(MapState())
    migrated["save_data_version"] = 13
    return migrated


def _migrate_v13_to_v14(document: dict[str, Any]) -> dict[str, Any]:
    legacy = _object(document, "$", _V13_GAME_STATE_FIELDS)
    migrated = deepcopy(legacy)
    legacy_hunger = _object(
        migrated["hunger"],
        "hunger",
        ("mild_population", "severe_population", "starving_population"),
    )
    legacy_population = _object(
        migrated["population"], "population", _field_names(PopulationState)
    )
    legacy_daily = _object(
        migrated["daily_survival"],
        "daily_survival",
        _field_names(DailySurvivalState),
    )
    legacy_resources = _object(
        migrated["resources"], "resources", _field_names(ResourceState)
    )
    alive = _integer(
        legacy_population["population_alive"],
        "population.population_alive",
        minimum=0,
    )
    last_unfed = _integer(
        legacy_daily["unfed_population"],
        "daily_survival.unfed_population",
        minimum=0,
    )
    light = _integer(
        legacy_hunger["mild_population"],
        "hunger.mild_population",
        minimum=0,
    )
    severe = _integer(
        legacy_hunger["severe_population"],
        "hunger.severe_population",
        minimum=0,
    )
    starving = _integer(
        legacy_hunger["starving_population"],
        "hunger.starving_population",
        minimum=0,
    )
    if light + severe + starving == 0 and last_unfed > 0:
        light = min(last_unfed, alive)
    migrated["cold_exposure"] = to_primitive(ColdExposureState())
    frost = dict(
        _object(
            migrated["final_frost"],
            "final_frost",
            _V13_FINAL_FROST_FIELDS,
        )
    )
    legacy_frost_entered = _boolean(
        frost["entered"], "final_frost.entered"
    )
    frost["wood_supply_check_day"] = 49 if legacy_frost_entered else None
    frost["wood_supply_surface_exhausted"] = False
    frost["wood_supply_logging_camp_available"] = False
    frost["wood_supply_wood_stock"] = (
        _integer(legacy_resources["wood"], "resources.wood", minimum=0)
        if legacy_frost_entered
        else 0
    )
    frost["wood_supply_logging_cost"] = 35 if legacy_frost_entered else 0
    frost["wood_supply_alternative_available"] = False
    frost["wood_supply_legacy_exempt"] = legacy_frost_entered
    frost["wood_supply_locked"] = False
    raw_records = frost["daily_records"]
    if not isinstance(raw_records, Mapping):
        raise SaveDataError("final_frost.daily_records must be an object")
    records = dict(raw_records)
    if any(
        not isinstance(day, str)
        or not day.isdigit()
        or str(int(day)) != day
        for day in records
    ):
        raise SaveDataError(
            "final_frost.daily_records keys must be canonical days"
        )
    legacy_record_days = sorted(int(day) for day in records)
    frost["legacy_hunger_history_unknown"] = bool(legacy_record_days)
    frost["legacy_hunger_record_days"] = legacy_record_days
    migrated_records: dict[str, Any] = {}
    for day, raw_record in records.items():
        path = f"final_frost.daily_records.{day}"
        legacy_record = dict(
            _object(raw_record, path, _V13_FROST_DAY_FIELDS)
        )
        record = to_primitive(
            _decode_frost_day_record(
                {
                    **legacy_record,
                    "unfed_population": 0,
                    "raw_hunger_deaths": 0,
                    "hunger_death_overflow": 0,
                },
                path,
            )
        )
        # v13 food deaths were settled outside the natural-death cap. Preserve
        # them as exact history without pretending they used the v14 slot.
        record["raw_hunger_deaths"] = 0
        record["hunger_death_overflow"] = 0
        migrated_records[day] = record
    frost["daily_records"] = migrated_records
    frost_records = list(migrated_records.values())
    frost["frost_hunger_days"] = 0
    frost["frost_unfed_person_days"] = 0
    frost["frost_population_person_days"] = sum(
        record["population_start"] for record in frost_records
    )
    frost["frost_peak_unfed_count"] = 0
    frost["frost_peak_population_start"] = 0
    frost["frost_hunger_deaths"] = sum(
        record["food_deaths"] for record in frost_records
    )
    migrated["final_frost"] = frost
    global_unfed_days = frost["frost_hunger_days"]
    global_unfed_person_days = frost["frost_unfed_person_days"]
    peak_unfed = frost["frost_peak_unfed_count"]
    peak_population = frost["frost_peak_population_start"]
    if not frost_records and last_unfed > 0:
        global_unfed_days = 1
        global_unfed_person_days = last_unfed
        peak_unfed = last_unfed
        peak_population = alive
    migrated["hunger"] = {
        "none_population": max(alive - light - severe - starving, 0),
        "light_population": light,
        "severe_population": severe,
        "starving_population": starving,
        "illness_remainder": 0,
        "severe_remainder": 0,
        "death_remainder": 0,
        "trust_remainder": 0,
        "panic_remainder": 0,
        "total_hunger_days": global_unfed_days,
        "total_unfed_person_days": global_unfed_person_days,
        "peak_unfed_count": peak_unfed,
        "peak_unfed_population_start": peak_population,
        "hunger_deaths_total": frost["frost_hunger_deaths"],
    }
    legacy_events = migrated.get("events")
    if isinstance(legacy_events, Mapping):
        migrated_events = dict(legacy_events)
        legacy_metrics = migrated_events.get("metrics")
        if isinstance(legacy_metrics, Mapping):
            migrated_metrics = dict(legacy_metrics)
            for name in (
                "cold_exposure_snapshot_day",
                "homeless_population",
                "cold_exposure_level",
            ):
                migrated_metrics.pop(name, None)
            migrated_metrics["cold_exposure_warning_streak"] = 0
            migrated_events["metrics"] = migrated_metrics
            migrated["events"] = migrated_events
    final_result = dict(migrated["final_result"])
    report = dict(final_result["report"])
    report["limiting_factor_ids"] = []
    final_result["report"] = report
    migrated["final_result"] = final_result
    migrated["save_data_version"] = 14
    return migrated


def _validate_state_invariants(
    state: GameState, *, strict_event_timeline: bool = True
) -> None:
    population = state.population
    map_state = state.map
    technologies = state.technologies
    events = state.events
    promises = state.promises
    if map_state.selection_mode not in {
        "random",
        "manual",
        "legacy_default",
    }:
        raise SaveDataError("unsupported map selection mode")
    if map_state.map_key not in {
        "rustbone_tundra",
        "black_ash_lowland",
        "twin_source_rift",
    }:
        raise SaveDataError("unsupported map key")
    if map_state.initial_hunting_grounds > map_state.total_hunting_grounds:
        raise SaveDataError(
            "initial hunting grounds cannot exceed total hunting grounds"
        )
    if len(set(events.resolved_event_ids)) != len(events.resolved_event_ids):
        raise SaveDataError("resolved event ids must be unique")
    if len(set(events.suppressed_event_ids_today)) != len(
        events.suppressed_event_ids_today
    ):
        raise SaveDataError("suppressed event ids must be unique")
    if len(set(events.status_ids)) != len(events.status_ids):
        raise SaveDataError("event status ids must be unique")
    legal_settled_day = max(
        state.calendar.current_day - 1,
        state.daily_survival.settled_day or 0,
    )
    exposure_snapshot_fields = {
        "cold_exposure_snapshot_day",
        "homeless_population",
        "cold_exposure_level",
    }
    present_exposure_snapshot_fields = exposure_snapshot_fields & set(
        events.metrics
    )
    if present_exposure_snapshot_fields and (
        present_exposure_snapshot_fields != exposure_snapshot_fields
    ):
        raise SaveDataError(
            "cold exposure snapshot must retain day, population, and level"
        )
    if present_exposure_snapshot_fields:
        exposure_snapshot_day = events.metrics[
            "cold_exposure_snapshot_day"
        ]
        homeless_snapshot = events.metrics["homeless_population"]
        exposure_level = events.metrics["cold_exposure_level"]
        if exposure_snapshot_day != legal_settled_day:
            raise SaveDataError(
                "cold exposure snapshot must describe the latest settled day"
            )
        if (
            homeless_snapshot < 0
            or homeless_snapshot > population.population_total_ever
            or not 0 <= exposure_level <= 5
        ):
            raise SaveDataError("cold exposure snapshot is outside its range")
        if (homeless_snapshot == 0) != (exposure_level == 0):
            raise SaveDataError(
                "cold exposure level must match whether homelessness exists"
            )
    for name, days in (
        ("recent_raw_food_days", events.recent_raw_food_days),
        ("recent_canteen_outage_days", events.recent_canteen_outage_days),
        ("recent_overtime_days", events.recent_overtime_days),
    ):
        if days != sorted(set(days)):
            raise SaveDataError(f"events.{name} must be sorted and unique")
        if any(day > legal_settled_day for day in days):
            raise SaveDataError(f"events.{name} cannot contain an unsettled day")
    if set(events.fixed_arrival_pressure_days) - set(_FIXED_ARRIVAL_DAYS):
        raise SaveDataError("arrival pressure history contains an unknown event")
    for event_id, days in events.fixed_arrival_pressure_days.items():
        if events.fixed_arrival_choices.get(event_id) in {None, "reject"}:
            raise SaveDataError(
                "arrival pressure history requires an accepted arrival"
            )
        if days != sorted(set(days)):
            raise SaveDataError("arrival pressure days must be sorted and unique")
        start_day = _FIXED_ARRIVAL_DAYS[event_id]
        if any(
            day < start_day
            or day > start_day + 4
            or day > legal_settled_day
            for day in days
        ):
            raise SaveDataError(
                "arrival pressure day is outside its settled five-day window"
            )
    for raw_day, pressure in events.natural_death_overflow_candidates.items():
        if (
            not raw_day.isdigit()
            or str(int(raw_day)) != raw_day
            or not 49 <= int(raw_day) <= 55
            or int(raw_day) > legal_settled_day
            or pressure <= 0
        ):
            raise SaveDataError(
                "natural death overflow candidate is not a settled frost fact"
            )
    resolution_promise_ids: set[str] = set()
    resolution_instances: dict[str, EventResolutionRecord] = {}
    resolution_occurrences: set[tuple[str, int]] = set()
    resolutions_by_event_id: dict[str, list[EventResolutionRecord]] = {}
    for resolution in events.resolution_history:
        if resolution.event_id not in events.resolved_event_ids:
            raise SaveDataError("event history must reference a resolved event")
        if resolution.event_type not in {"major", "normal"}:
            raise SaveDataError("event history contains an unsupported event type")
        if resolution.resolved_day > state.calendar.current_day:
            raise SaveDataError("event history cannot come from a future day")
        if (
            resolution.occurrence_index
            > events.occurrence_counts.get(resolution.event_id, 0)
            or resolution.instance_id
            != _event_instance_id(
                resolution.event_id, resolution.occurrence_index
            )
        ):
            raise SaveDataError(
                "event history contains an invalid instance identity"
            )
        occurrence_key = (
            resolution.event_id,
            resolution.occurrence_index,
        )
        if (
            resolution.instance_id in resolution_instances
            or occurrence_key in resolution_occurrences
        ):
            raise SaveDataError(
                "event history instance identities must be unique"
            )
        resolution_instances[resolution.instance_id] = resolution
        resolution_occurrences.add(occurrence_key)
        resolutions_by_event_id.setdefault(
            resolution.event_id, []
        ).append(resolution)
        if set(resolution.resource_changes) != {
            "coal", "wood", "steel", "raw_food", "cooked_food"
        }:
            raise SaveDataError("event history resource changes are incomplete")
        if resolution.promise_id is not None:
            _promise_sequence(resolution.promise_id)
            if resolution.promise_id in resolution_promise_ids:
                raise SaveDataError("a promise may only have one source event history")
            resolution_promise_ids.add(resolution.promise_id)
    major_count = 0
    normal_count = 0
    for event_id, event in events.active_events.items():
        if event.event_id != event_id:
            raise SaveDataError("active event id must match its map key")
        if (
            events.occurrence_counts.get(event_id, 0) < 1
            or event.occurrence_index
            != events.occurrence_counts.get(event_id, 0)
            or event.instance_id
            != _event_instance_id(event_id, event.occurrence_index)
            or event.instance_id in resolution_instances
        ):
            raise SaveDataError("active events must be counted when displayed")
        # resolved_event_ids is the historical set of event types, so a
        # repeatable event may legitimately have a later active occurrence.
        # Every resolved instance must precede it by both identity and day;
        # ignored occurrences do not need a history record.
        if event_id in events.resolved_event_ids:
            prior_resolutions = resolutions_by_event_id.get(event_id, [])
            if not prior_resolutions:
                raise SaveDataError(
                    "active repeat event lacks a prior resolution history"
                )
            if any(
                resolution.occurrence_index >= event.occurrence_index
                or resolution.resolved_day >= event.trigger_day
                for resolution in prior_resolutions
            ):
                raise SaveDataError(
                    "active repeat event must follow every prior resolution"
                )
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
    for event_id, arrival_day in (
        _FIXED_ARRIVAL_DAYS.items() if strict_event_timeline else ()
    ):
        choice = events.fixed_arrival_choices.get(event_id)
        histories = [
            item for item in events.resolution_history if item.event_id == event_id
        ]
        resolved = event_id in events.resolved_event_ids
        active = event_id in events.active_events
        count = events.occurrence_counts.get(event_id, 0)
        if active:
            if (
                events.generated_for_day != arrival_day
                or state.calendar.current_day != arrival_day
                or choice is not None
                or resolved
                or histories
                or count != 1
            ):
                raise SaveDataError("active fixed arrival state is inconsistent")
            continue
        if choice is not None:
            if (
                not resolved
                or count != 1
                or len(histories) != 1
                or histories[0].option_id != choice
                or histories[0].event_type != "major"
                or histories[0].resolved_day != arrival_day
            ):
                raise SaveDataError(
                    "fixed arrival choice, history, and resolution disagree"
                )
            continue
        if resolved or histories or count or state.calendar.current_day > arrival_day:
            raise SaveDataError("a past fixed arrival cannot be skipped")
        if (
            state.calendar.current_day == arrival_day
            and events.generated_for_day == arrival_day
        ):
            raise SaveDataError(
                "today's generated fixed arrival must remain active or resolved"
            )
    if set(events.pending_followups) - set(_EVENT_FOLLOWUPS):
        raise SaveDataError("state contains an unsupported event followup command")
    expected_followup_instances = {
        resolution.instance_id: command_name
        for command_name, source in _EVENT_FOLLOWUPS.items()
        for resolution in events.resolution_history
        if (resolution.event_id, resolution.option_id) == source
    }
    lifecycle_instances: set[str] = set()
    for command_name, followup in events.pending_followups.items():
        expected_event, expected_option = _EVENT_FOLLOWUPS[command_name]
        source = resolution_instances.get(followup.instance_id)
        if (
            followup.command_name != command_name
            or followup.event_id != expected_event
            or followup.option_id != expected_option
            or followup.created_day > state.calendar.current_day
            or followup.occurrence_index
            > events.occurrence_counts.get(followup.event_id, 0)
            or followup.instance_id
            != _event_instance_id(
                followup.event_id, followup.occurrence_index
            )
            or source is None
            or source.event_id != followup.event_id
            or source.option_id != followup.option_id
            or source.resolved_day != followup.created_day
            or source.occurrence_index != followup.occurrence_index
            or expected_followup_instances.get(followup.instance_id)
            != command_name
        ):
            raise SaveDataError("event followup state disagrees with its source")
        if followup.instance_id in lifecycle_instances:
            raise SaveDataError(
                "an event followup instance may only have one lifecycle record"
            )
        lifecycle_instances.add(followup.instance_id)

    consumed_sequences: list[int] = []
    for followup in events.consumed_followups:
        expected_source = _EVENT_FOLLOWUPS.get(followup.command_name)
        source = resolution_instances.get(followup.instance_id)
        if (
            expected_source is None
            or expected_source != (followup.event_id, followup.option_id)
            or followup.created_day > followup.settled_day
            or followup.settled_day > state.calendar.current_day
            or followup.settled_command_sequence > state.command_sequence
            or followup.instance_id
            != _event_instance_id(
                followup.event_id, followup.occurrence_index
            )
            or source is None
            or source.event_id != followup.event_id
            or source.option_id != followup.option_id
            or source.resolved_day != followup.created_day
            or source.occurrence_index != followup.occurrence_index
            or expected_followup_instances.get(followup.instance_id)
            != followup.command_name
        ):
            raise SaveDataError(
                "consumed event followup disagrees with its source"
            )
        if followup.instance_id in lifecycle_instances:
            raise SaveDataError(
                "an event followup instance may only have one lifecycle record"
            )
        lifecycle_instances.add(followup.instance_id)
        consumed_sequences.append(followup.settled_command_sequence)
    if consumed_sequences != sorted(set(consumed_sequences)):
        raise SaveDataError(
            "consumed event followups must use unique command sequence order"
        )
    if lifecycle_instances != set(expected_followup_instances):
        raise SaveDataError(
            "every event followup source must retain one lifecycle record"
        )
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
    promise_ids = set(promises.active_promises) | settled_promises
    if resolution_promise_ids != promise_ids:
        raise SaveDataError("every promise must have exactly one source event history")
    all_promise_ids = (
        list(promises.active_promises)
        + promises.completed_promise_ids
        + promises.failed_promise_ids
        + [item.promise_id for item in promises.settlement_history]
    )
    promise_sequences = [_promise_sequence(item) for item in all_promise_ids]
    if promises.next_sequence <= max(promise_sequences, default=0):
        raise SaveDataError("next promise sequence must exceed every existing promise id")
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
        source_history = [
            item
            for item in events.resolution_history
            if item.promise_id == settlement.promise_id
        ]
        if len(source_history) != 1:
            raise SaveDataError("promise settlement lacks its source event history")
        source_contract = _EVENT_PROMISES.get(source_history[0].event_id)
        if (
            source_contract is None
            or source_contract[0] != settlement.promise_type
            or source_history[0].option_id
            != f"promise_{settlement.promise_type}"
        ):
            raise SaveDataError("promise settlement disagrees with its source event")
        allowed_severities = {source_contract[1]}
        if source_history[0].event_id == "furnace_redline":
            allowed_severities.add("critical")
        if (
            source_history[0].event_id == "cold_house_night"
            and source_history[0].event_type == "major"
        ):
            allowed_severities.add("serious")
        if settlement.severity not in allowed_severities:
            raise SaveDataError(
                "promise settlement severity disagrees with its source event"
            )
    if settlement_ids != settled_promises:
        raise SaveDataError("settled promise ids and history must match exactly")
    for promise_id, promise in promises.active_promises.items():
        if promise.promise_id != promise_id:
            raise SaveDataError("active promise id must match its map key")
        if promise.promise_type in active_types:
            raise SaveDataError("only one active promise of each type is allowed")
        active_types.add(promise.promise_type)
        if promise.severity not in {"ordinary", "serious", "critical"}:
            raise SaveDataError("unsupported promise severity")
        source_contract = _EVENT_PROMISES.get(promise.source_event_id)
        if (
            source_contract is None
            or source_contract[0] != promise.promise_type
        ):
            raise SaveDataError("promise type disagrees with its source event")
        source_history = [
            item
            for item in events.resolution_history
            if item.promise_id == promise_id
        ]
        if (
            len(source_history) != 1
            or source_history[0].event_id != promise.source_event_id
            or source_history[0].option_id != f"promise_{promise.promise_type}"
            or source_history[0].resolved_day != promise.created_day
        ):
            raise SaveDataError("promise lacks its exact source event history")
        allowed_severities = {source_contract[1]}
        if promise.source_event_id == "furnace_redline":
            allowed_severities.add("critical")
        if (
            promise.source_event_id == "cold_house_night"
            and source_history[0].event_type == "major"
        ):
            allowed_severities.add("serious")
        if promise.severity not in allowed_severities:
            raise SaveDataError("promise severity disagrees with its source event")
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
    old_city = state.old_city
    old_city_stages = {"southern_letter", "rumors", "public_gathering", "countdown"}
    old_city_events = {
        "southern_letter", "rumors", "public_gathering", "countdown"
    }
    if old_city.active_stage_id is not None and old_city.active_stage_id not in old_city_stages:
        raise SaveDataError("old city active stage is unknown")
    if old_city.pending_event_id is not None and old_city.pending_event_id not in old_city_events:
        raise SaveDataError("old city pending event is unknown")
    if len(set(old_city.stage_events_seen)) != len(old_city.stage_events_seen):
        raise SaveDataError("old city stage event history must be unique")
    if (
        old_city.recent_major_death_days
        != sorted(set(old_city.recent_major_death_days))
        or any(
            day > state.calendar.current_day
            for day in old_city.recent_major_death_days
        )
    ):
        raise SaveDataError("old city recent major death days are invalid")
    if set(old_city.stage_events_seen) - old_city_events:
        raise SaveDataError("old city stage event history is unknown")
    stage_order = ["southern_letter", "rumors", "public_gathering", "countdown"]
    if old_city.stage_events_seen != stage_order[: len(old_city.stage_events_seen)]:
        raise SaveDataError("old city stage history must follow canonical order")
    if old_city.pending_event_id is not None and (
        old_city.pending_event_id != old_city.active_stage_id
        or old_city.pending_event_id not in old_city.stage_events_seen
    ):
        raise SaveDataError("old city pending event must match its active stage")
    if old_city.member_count > population.population_alive:
        raise SaveDataError("old city members cannot exceed living population")
    if (
        old_city.hidden_growth_days_remaining > 3
        or old_city.last_daily_trend < -8
        or old_city.last_daily_trend > 16
    ):
        raise SaveDataError("old city daily trend state is out of range")
    if old_city.is_unlocked:
        if old_city.reference_population <= 0:
            raise SaveDataError("unlocked old city requires a reference population")
        if not (
            0 < old_city.low_threshold
            <= old_city.middle_threshold
            <= old_city.high_threshold
        ):
            raise SaveDataError("old city thresholds must be ordered")
    elif any(
        (
            old_city.reference_population,
            old_city.member_count,
            old_city.low_threshold,
            old_city.middle_threshold,
            old_city.high_threshold,
            old_city.hidden_growth_days_remaining,
            old_city.actual_departures,
            old_city.theoretical_departures,
            old_city.protected_engineers,
            old_city.settlement_member_count,
            len(old_city.protected_jobs),
            len(old_city.settlement_resource_losses),
            len(old_city.recent_major_death_days),
            old_city.reduction_reason is not None,
        )
    ):
        raise SaveDataError("locked old city cannot retain Patch 008 values")
    if old_city.resolved:
        alive_before_departure = (
            population.population_alive + old_city.actual_departures
        )
        if (
            old_city.result_id not in {"scattered", "partial_exodus", "large_exodus"}
            or old_city.settlement_day is None
            or old_city.settlement_day > state.calendar.current_day
            or old_city.settlement_day > 48
            or old_city.active_stage_id is not None
            or old_city.pending_event_id is not None
            or old_city.member_count != 0
            or old_city.settlement_member_count > alive_before_departure
            or set(old_city.settlement_resource_losses)
            != {"cooked_food", "coal", "wood", "steel"}
        ):
            raise SaveDataError("resolved old city state is incomplete")
        if old_city.settlement_member_count < old_city.low_threshold:
            expected_result = "scattered"
            expected_theoretical = 0
        elif old_city.settlement_member_count < old_city.high_threshold:
            expected_result = "partial_exodus"
            expected_theoretical = min(
                old_city.settlement_member_count * 40 // 100,
                alive_before_departure * 12 // 100,
            )
        else:
            expected_result = "large_exodus"
            expected_theoretical = min(
                old_city.settlement_member_count * 55 // 100,
                alive_before_departure * 22 // 100,
            )
        if (
            old_city.result_id != expected_result
            or old_city.theoretical_departures != expected_theoretical
            or old_city.actual_departures > old_city.theoretical_departures
        ):
            raise SaveDataError("old city departure summary disagrees with its tier")
        if (
            old_city.actual_departures == old_city.theoretical_departures
            and old_city.reduction_reason is not None
        ) or (
            old_city.actual_departures < old_city.theoretical_departures
            and old_city.reduction_reason
            not in {
                "critical_job_protection",
                "engineer_floor",
                "critical_jobs_and_engineer_floor",
                "population_protection",
            }
        ):
            raise SaveDataError("old city departure reduction reason is inconsistent")
        if old_city.protected_engineers > 2:
            raise SaveDataError("old city engineer protection summary is invalid")
        if old_city.theoretical_departures == 0:
            if (
                old_city.protected_jobs
                or old_city.protected_engineers
                or old_city.reduction_reason is not None
            ):
                raise SaveDataError(
                    "old city zero-departure summary cannot retain protections"
                )
        for target_id, protected_count in old_city.protected_jobs.items():
            if protected_count != 1:
                raise SaveDataError("old city protected jobs must retain one worker")
            kind, separator, target = target_id.partition(":")
            if not separator or kind not in {"building", "resource"}:
                raise SaveDataError("old city protected job id is invalid")
            if kind == "building":
                building = state.buildings.get(target)
                if (
                    building is None
                    or building.building_type
                    not in {
                        "medical_station",
                        "hospital",
                        "canteen",
                        "hunting_lodge",
                        "greenhouse",
                        "improved_greenhouse",
                        "small_coal_miner",
                    }
                ):
                    raise SaveDataError("old city protected building summary is invalid")
            else:
                point = state.surface_resource_points.get(target)
                if (
                    point is None
                    or point.resource_type != "coal"
                ):
                    raise SaveDataError("old city protected resource summary is invalid")
        departed = old_city.actual_departures
        theoretical_losses = (
            {
                "cooked_food": departed,
                "coal": departed * 2,
                "wood": departed,
                "steel": departed // 2,
            }
            if old_city.result_id == "partial_exodus"
            else {
                "cooked_food": departed * 2,
                "coal": departed * 3,
                "wood": departed * 2,
                "steel": departed,
            }
            if old_city.result_id == "large_exodus"
            else {"cooked_food": 0, "coal": 0, "wood": 0, "steel": 0}
        )
        for resource, theoretical_loss in theoretical_losses.items():
            actual_loss = old_city.settlement_resource_losses[resource]
            if actual_loss > theoretical_loss:
                raise SaveDataError("old city resource loss summary is inconsistent")
    elif (
        old_city.result_id is not None
        or old_city.settlement_day is not None
        or old_city.settlement_member_count
        or old_city.theoretical_departures
        or old_city.actual_departures
        or old_city.protected_jobs
        or old_city.protected_engineers
        or old_city.reduction_reason is not None
        or old_city.settlement_resource_losses
    ):
        raise SaveDataError("unresolved old city cannot have a settlement result")
    if old_city.is_unlocked and old_city.reference_population > 0:
        if not old_city.stage_events_seen:
            raise SaveDataError("unlocked old city requires a stage history")
        if not old_city.resolved and old_city.active_stage_id != old_city.stage_events_seen[-1]:
            raise SaveDataError("old city active stage must match stage history")
        if ("countdown" in old_city.stage_events_seen) != (
            old_city.countdown_day is not None
        ):
            raise SaveDataError("old city countdown must match stage history")
        if old_city.countdown_day is not None and not (
            24 <= old_city.countdown_day <= 48
        ):
            raise SaveDataError("old city countdown must end by day 48")
        if (
            not old_city.resolved
            and old_city.countdown_day is not None
            and state.calendar.current_day > old_city.countdown_day
        ):
            raise SaveDataError("old city countdown cannot remain unresolved after its deadline")
    promise_fields = (
        old_city.promise_created_day,
        old_city.promise_deadline_day,
        old_city.promise_target_count,
    )
    if old_city.promise_active:
        if (
            any(value is None for value in promise_fields)
            or old_city.promise_settled
            or old_city.promise_outcome is not None
            or old_city.promise_settled_day is not None
        ):
            raise SaveDataError("active old city promise is incomplete")
    elif not old_city.promise_settled and any(value is not None for value in promise_fields):
        raise SaveDataError("inactive old city promise cannot retain an open contract")
    if old_city.promise_settled:
        if (
            old_city.promise_outcome not in {"success", "failure"}
            or any(value is None for value in promise_fields)
            or old_city.promise_settled_day is None
            or old_city.promise_settled_day < old_city.promise_created_day
            or old_city.promise_settled_day > state.calendar.current_day
        ):
            raise SaveDataError("settled old city promise is incomplete")
        if (
            old_city.promise_outcome == "success"
            and old_city.promise_settled_day > old_city.promise_deadline_day + 1
        ) or (
            old_city.promise_outcome == "failure"
            and old_city.promise_settled_day
            != old_city.promise_deadline_day + 1
        ):
            raise SaveDataError("old city promise outcome disagrees with its deadline")
    elif (
        old_city.promise_outcome is not None
        or old_city.promise_settled_day is not None
    ):
        raise SaveDataError("unsettled old city promise cannot have an outcome")
    if (
        (old_city.promise_active or old_city.promise_settled)
        and "countdown" not in old_city.stage_events_seen
    ):
        raise SaveDataError("old city promise requires the countdown stage")

    oath_order = state.oath_order
    if oath_order.selected_route not in {None, "oath", "iron"}:
        raise SaveDataError("unsupported oath/order route")
    if len(set(oath_order.signed_law_ids)) != len(oath_order.signed_law_ids):
        raise SaveDataError("oath/order signed laws must be unique")
    if set(oath_order.law_signed_days) != set(oath_order.signed_law_ids):
        raise SaveDataError("oath/order signing history must match signed laws")
    if any(
        day < 1 or day > state.calendar.current_day
        for day in oath_order.law_signed_days.values()
    ):
        raise SaveDataError("oath/order signing history cannot be in the future")
    if len(set(oath_order.law_signed_days.values())) != len(
        oath_order.law_signed_days
    ):
        raise SaveDataError("only one oath/order law may be signed per day")
    expected_next_law_day = (
        max(oath_order.law_signed_days.values()) + 2
        if oath_order.law_signed_days
        else 1
    )
    if oath_order.next_law_day != expected_next_law_day:
        raise SaveDataError("oath/order signing cooldown is inconsistent")
    if len(set(oath_order.ending_tag_candidates)) != len(
        oath_order.ending_tag_candidates
    ):
        raise SaveDataError("oath/order ending tags must be unique")
    if oath_order.selected_route is None:
        if oath_order.signed_law_ids or oath_order.final_oath_active or oath_order.highest_order_active:
            raise SaveDataError("unselected oath/order route cannot have signed laws")
    elif not oath_order.signed_law_ids:
        raise SaveDataError("selected oath/order route requires its entry law")
    elif not oath_order.page_unlocked:
        raise SaveDataError("selected oath/order route requires an unlocked page")
    oath_enabled = oath_order.selected_route == "oath"
    iron_enabled = oath_order.selected_route == "iron"
    for facility, expected in (
        (oath_order.oath_hall, oath_enabled),
        (oath_order.patrol_office, iron_enabled),
    ):
        if facility.enabled != expected or facility.visible != expected:
            raise SaveDataError("route facility visibility must match selected route")
        if not expected and (
            facility.assigned_workers
            or facility.assigned_engineers
            or facility.is_running
        ):
            raise SaveDataError("disabled route facility cannot retain staffing")
        if facility.is_running != (
            expected and facility.assigned_workers + facility.assigned_engineers >= 1
        ):
            raise SaveDataError("route facility running state must match staffing")
    if oath_order.final_oath_active and "final_oath" not in oath_order.signed_law_ids:
        raise SaveDataError("final oath state requires its signed law")
    if oath_order.highest_order_active and "highest_order" not in oath_order.signed_law_ids:
        raise SaveDataError("highest order state requires its signed law")
    if oath_order.final_oath_active and oath_order.highest_order_active:
        raise SaveDataError("final oath and highest order are mutually exclusive")
    known_oath_order_tags = {
        "oath_carried_zero_trust",
        "decree_carried_panic",
    }
    if set(oath_order.ending_tag_candidates) - known_oath_order_tags:
        raise SaveDataError("unknown oath/order ending tag")
    if (
        "oath_carried_zero_trust" in oath_order.ending_tag_candidates
        and not oath_order.final_oath_active
    ) or (
        "decree_carried_panic" in oath_order.ending_tag_candidates
        and not oath_order.highest_order_active
    ):
        raise SaveDataError("oath/order ending tag lacks its terminal law")
    if set(oath_order.action_next_available_day) != set(
        oath_order.action_last_used_day
    ):
        raise SaveDataError("route action history and cooldown keys must match")
    if any(
        day < 1 or day > state.calendar.current_day
        for day in oath_order.action_last_used_day.values()
    ):
        raise SaveDataError("route action history cannot be in the future")
    if (
        oath_order.death_panic_aftershock_halved_day is not None
        and oath_order.death_panic_aftershock_halved_day
        != state.calendar.current_day
    ):
        raise SaveDataError("mourning-bell modifier must belong to the current day")
    if (
        oath_order.death_panic_aftershock_halved_day is not None
        and oath_order.action_last_used_day.get("mourning_bell")
        != oath_order.death_panic_aftershock_halved_day
    ):
        raise SaveDataError("mourning-bell modifier lacks its action history")
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
    if population.population_total_ever != (
        population.population_total + state.old_city.actual_departures
    ):
        raise SaveDataError(
            "historical population must retain every resident and departure"
        )
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
        state.hunger.none_population
        + state.hunger.light_population
        + state.hunger.severe_population
        + state.hunger.starving_population
    )
    if hunger_total != population.population_alive:
        raise SaveDataError("hunger pools must equal living population")
    for name, maximum in (
        ("illness_remainder", 4),
        ("severe_remainder", 5),
        ("death_remainder", 7),
        ("trust_remainder", 19),
        ("panic_remainder", 14),
    ):
        if getattr(state.hunger, name) > maximum:
            raise SaveDataError(f"hunger.{name} exceeds its integer range")
    if state.hunger.total_hunger_days > FINAL_DAY:
        raise SaveDataError("total hunger days cannot exceed the campaign")
    if (
        state.hunger.peak_unfed_count
        > state.hunger.peak_unfed_population_start
        or (
            state.hunger.peak_unfed_count == 0
            and state.hunger.peak_unfed_population_start != 0
        )
    ):
        raise SaveDataError("global hunger peak ratio is inconsistent")
    if (
        (state.hunger.total_hunger_days == 0)
        != (state.hunger.total_unfed_person_days == 0)
        or (
            state.hunger.total_hunger_days == 0
            and state.hunger.peak_unfed_count != 0
        )
        or state.hunger.peak_unfed_count
        > state.hunger.total_unfed_person_days
        or state.hunger.hunger_deaths_total > population.population_dead
    ):
        raise SaveDataError("global hunger statistics are inconsistent")
    if (
        state.hunger.light_population
        + state.hunger.severe_population
        + state.hunger.starving_population
        == 0
        and any(
            (
                state.hunger.illness_remainder,
                state.hunger.severe_remainder,
                state.hunger.death_remainder,
                state.hunger.trust_remainder,
                state.hunger.panic_remainder,
            )
        )
    ):
        raise SaveDataError("inactive hunger pools cannot retain remainders")
    if (
        state.hunger.severe_population
        + state.hunger.starving_population
        == 0
        and state.hunger.severe_remainder != 0
    ):
        raise SaveDataError("inactive severe hunger cannot retain a remainder")
    if (
        state.hunger.starving_population == 0
        and state.hunger.death_remainder != 0
    ):
        raise SaveDataError("inactive starvation cannot retain a death remainder")
    exposure_key = re.compile(
        r"^(?:[0-5]|level_[0-5]_(?:base|consecutive|frost_extra))$"
    )
    for name in _field_names(ColdExposureState):
        values = getattr(state.cold_exposure, name)
        if any(not exposure_key.fullmatch(key) for key in values):
            raise SaveDataError(f"cold_exposure.{name} contains an invalid key")

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
    if medical.sick_treatment_progress > 2:
        raise SaveDataError(
            "sick treatment progress must remain below one recovery unit"
        )

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

    frost = state.final_frost
    all_record_days = sorted(int(key) for key in frost.daily_records)
    legacy_record_days = frost.legacy_hunger_record_days
    if (
        frost.legacy_hunger_history_unknown != bool(legacy_record_days)
        or legacy_record_days != sorted(set(legacy_record_days))
        or legacy_record_days != all_record_days[: len(legacy_record_days)]
        or (legacy_record_days and not frost.wood_supply_legacy_exempt)
    ):
        raise SaveDataError(
            "legacy hunger compatibility requires migrated frost history"
        )
    if frost.entered != (frost.baseline_day is not None):
        raise SaveDataError("final frost entry and baseline day must agree")
    if frost.entered and frost.baseline_day != 49:
        raise SaveDataError("final frost baseline must be captured on day 49")
    baseline_health = (
        frost.baseline_healthy_population
        + frost.baseline_sick_population
        + frost.baseline_critical_population
        + frost.baseline_disabled_population
    )
    if frost.entered and baseline_health != frost.baseline_alive_population:
        raise SaveDataError("final frost baseline health pools must match alive population")
    if frost.baseline_disabled_population > frost.baseline_alive_population:
        raise SaveDataError("final frost disabled baseline exceeds alive population")
    if frost.baseline_workable_population > frost.baseline_alive_population:
        raise SaveDataError("final frost workable baseline exceeds alive population")
    if frost.prepared_item_count > 8 or frost.unprepared_item_count > 8:
        raise SaveDataError("final frost preparation count exceeds its eight checks")
    if len(set(frost.preparation_tags)) != len(frost.preparation_tags):
        raise SaveDataError("final frost preparation tags must be unique")
    if {"prepared_for_frost", "unprepared_frost"}.issubset(
        frost.preparation_tags
    ):
        raise SaveDataError("final frost preparation tags must be mutually exclusive")
    if frost.pending_extreme_crisis_conditions:
        raise SaveDataError(
            "saved state cannot retain pending extreme crisis conditions"
        )
    if set(frost.preparation_tags) - {
        "prepared_for_frost",
        "unprepared_frost",
    }:
        raise SaveDataError("unsupported final frost preparation tag")
    if not frost.entered and (
        frost.daily_records
        or frost.frost_deaths
        or frost.final_score_day is not None
        or frost.preparation_tags
    ):
        raise SaveDataError("inactive final frost cannot retain settlement facts")
    if state.calendar.current_day >= 49 and not frost.entered:
        raise SaveDataError("D49+ state must retain its final frost baseline")
    if frost.entered and state.calendar.current_day < 49:
        raise SaveDataError("final frost baseline cannot exist before D49")
    record_days = all_record_days
    latest_required_day = min(55, legal_settled_day)
    expected_record_days = (
        list(range(49, latest_required_day + 1))
        if latest_required_day >= 49
        else []
    )
    if record_days != expected_record_days:
        raise SaveDataError(
            "final frost records must cover every settled day from D49"
        )
    previous_population: int | None = None
    total_recorded_deaths = 0
    for key in sorted(frost.daily_records, key=int):
        record = frost.daily_records[key]
        if record.day != int(key) or not 49 <= record.day <= 55:
            raise SaveDataError("final frost record key must match a D49-D55 day")
        if previous_population is None:
            if record.population_start != frost.baseline_alive_population:
                raise SaveDataError(
                    "first final frost record must start from the D49 baseline"
                )
        elif record.population_start != previous_population:
            raise SaveDataError("final frost daily population chain is discontinuous")
        if record.population_end > record.population_start:
            raise SaveDataError("final frost daily population cannot increase during settlement")
        is_legacy_record = record.day in legacy_record_days
        if not is_legacy_record and record.starvation != (
            record.unfed_population > 0
        ):
            raise SaveDataError(
                "final frost starvation flag must match the unfed population"
            )
        if (
            record.food_deaths
            + record.disease_deaths
            + record.cold_deaths
        ) > (
            record.population_start - record.population_end
        ):
            raise SaveDataError("final frost deaths exceed the daily population loss")
        if (
            record.homeless_new_sick > record.new_sick
            or record.homeless_new_disabled > record.new_disabled
            or record.homeless_cold_deaths > record.cold_deaths
            or (
                record.homeless_exposure_population == 0
                and (
                    record.homeless_new_sick
                    or record.homeless_new_disabled
                    or record.homeless_cold_deaths
                )
            )
        ):
            raise SaveDataError(
                "homeless frost harm must be attributed within daily totals"
            )
        total_recorded_deaths += (
            record.population_start - record.population_end
        )
        if record.extreme_crisis_conditions != sorted(
            set(record.extreme_crisis_conditions)
        ):
            raise SaveDataError(
                "extreme crisis conditions must be sorted and unique"
            )
        if set(record.extreme_crisis_conditions) - (
            _EXTREME_CRISIS_CONDITION_IDS
        ):
            raise SaveDataError(
                "final frost record contains an unknown extreme crisis condition"
            )
        expected_base_cap = min(
            22,
            12 + max(0, record.population_start - 80) // 35,
        )
        expected_applied_cap = (
            (expected_base_cap * 3 + 1) // 2
            if len(record.extreme_crisis_conditions) >= 2
            else expected_base_cap
        )
        if (
            record.base_natural_death_cap != expected_base_cap
            or record.applied_natural_death_cap != expected_applied_cap
        ):
            raise SaveDataError(
                "final frost natural death cap summary is inconsistent"
            )
        expected_disease_deaths = min(
            record.raw_disease_deaths, expected_applied_cap
        )
        expected_hunger_deaths = (
            record.food_deaths
            if is_legacy_record
            else min(
                record.raw_hunger_deaths,
                expected_applied_cap - expected_disease_deaths,
            )
        )
        expected_cold_deaths = min(
            record.raw_cold_deaths,
            expected_applied_cap
            - expected_disease_deaths
            - (
                0
                if is_legacy_record
                else expected_hunger_deaths
            ),
        )
        if (
            record.actual_disease_deaths != expected_disease_deaths
            or record.disease_deaths != expected_disease_deaths
            or record.disease_death_overflow
            != record.raw_disease_deaths - expected_disease_deaths
            or record.food_deaths != expected_hunger_deaths
            or (
                is_legacy_record
                and (
                    record.raw_hunger_deaths != 0
                    or record.hunger_death_overflow != 0
                )
            )
            or (
                not is_legacy_record
                and record.hunger_death_overflow
                != record.raw_hunger_deaths - expected_hunger_deaths
            )
            or record.actual_cold_deaths != expected_cold_deaths
            or record.cold_deaths != expected_cold_deaths
            or record.cold_death_overflow
            != record.raw_cold_deaths - expected_cold_deaths
            or record.natural_death_overflow_pressure
            != record.disease_death_overflow
            + record.hunger_death_overflow
            + record.cold_death_overflow
        ):
            raise SaveDataError(
                "final frost natural death allocation is inconsistent"
            )
        candidate_pressure = events.natural_death_overflow_candidates.get(key)
        if record.natural_death_overflow_pressure > 0:
            if candidate_pressure != record.natural_death_overflow_pressure:
                raise SaveDataError(
                    "natural death overflow lacks its exact event candidate"
                )
        elif candidate_pressure is not None:
            raise SaveDataError(
                "zero natural death overflow cannot retain an event candidate"
            )
        previous_population = record.population_end
    if set(events.natural_death_overflow_candidates) - set(
        frost.daily_records
    ):
        raise SaveDataError(
            "natural death overflow candidate lacks its frost record"
        )
    if frost.frost_deaths != total_recorded_deaths:
        raise SaveDataError("final frost death total must match daily records")
    records = list(frost.daily_records.values())
    expected_hunger_days = sum(
        record.unfed_population > 0 for record in records
    )
    expected_unfed_person_days = sum(
        record.unfed_population for record in records
    )
    expected_population_person_days = sum(
        record.population_start for record in records
    )
    expected_hunger_deaths = sum(record.food_deaths for record in records)
    peak_record: FrostDayRecord | None = None
    for candidate in records:
        if candidate.unfed_population == 0:
            continue
        if peak_record is None or (
            candidate.unfed_population * peak_record.population_start
            > peak_record.unfed_population * candidate.population_start
        ) or (
            candidate.unfed_population * peak_record.population_start
            == peak_record.unfed_population * candidate.population_start
            and candidate.unfed_population > peak_record.unfed_population
        ):
            peak_record = candidate
    expected_peak_count = peak_record.unfed_population if peak_record else 0
    expected_peak_population = (
        peak_record.population_start if peak_record else 0
    )
    if (
        frost.frost_hunger_days != expected_hunger_days
        or frost.frost_unfed_person_days != expected_unfed_person_days
        or frost.frost_population_person_days != expected_population_person_days
        or frost.frost_peak_unfed_count != expected_peak_count
        or frost.frost_peak_population_start != expected_peak_population
        or frost.frost_hunger_deaths != expected_hunger_deaths
    ):
        raise SaveDataError("final frost hunger statistics are inconsistent")
    if frost.final_score_day is not None and frost.final_score_day != 55:
        raise SaveDataError("final frost score may only be finalized on day 55")

    final = state.final_result
    for name, values in (
        ("ending_tags", final.ending_tags),
        ("major_tags", final.major_tags),
        ("defining_tags", final.defining_tags),
    ):
        if len(set(values)) != len(values):
            raise SaveDataError(f"final result {name} must be unique")
    if set(final.major_tags) & set(final.defining_tags):
        raise SaveDataError("major and defining ending tags must be disjoint")
    if (
        {"prepared_for_frost", "unprepared_frost"}.issubset(
            final.major_tags
        )
        or (
            "frost_survived_clean" in final.major_tags
            and "frost_survived_broken" in final.defining_tags
        )
    ):
        raise SaveDataError("opposing final frost tags must be mutually exclusive")
    if final.is_finalized:
        if final.hard_fail_type is not None:
            if final.ending_id not in {None, "hard_fail"}:
                raise SaveDataError("hard fail has an unsupported ending id")
            if final.system_scores or final.total_score is not None:
                raise SaveDataError("hard fail cannot retain survival scores")
            if final.major_tags or final.defining_tags:
                raise SaveDataError("hard fail cannot retain survival tag groups")
            expected_hard_fail_tags = (
                []
                if final.ending_id is None
                else ["hard_fail", final.hard_fail_type.value]
            )
            if final.ending_tags != expected_hard_fail_tags:
                raise SaveDataError("hard fail ending tags are not canonical")
        else:
            if final.ending_id not in _FINAL_ENDING_IDS - {"hard_fail"}:
                raise SaveDataError("finalized state has an unsupported ending id")
            if set(final.system_scores) != _FINAL_SYSTEM_IDS:
                raise SaveDataError("survival result must contain all six system scores")
            if any(score > 4 for score in final.system_scores.values()):
                raise SaveDataError("final system scores must be between zero and four")
            if final.total_score != sum(final.system_scores.values()):
                raise SaveDataError("final total score must equal the six system scores")
            if frost.final_score_day != 55:
                raise SaveDataError("survival result requires a D55 frost score")
            if final.ending_tags != [
                final.ending_id,
                *final.major_tags,
                *final.defining_tags,
            ]:
                raise SaveDataError(
                    "survival ending tags must match the structured result"
                )
    elif (
        final.ending_id is not None
        or final.ending_tags
        or final.system_scores
        or final.total_score is not None
        or final.major_tags
        or final.defining_tags
    ):
        raise SaveDataError("unfinished result cannot retain final scoring fields")

    if final.run_state is RunState.ACTIVE:
        if (
            final.termination_reason is not None
            or final.termination_day is not None
            or final.termination_command_sequence is not None
        ):
            raise SaveDataError(
                "active run cannot retain termination history"
            )
    elif final.run_state is RunState.ENDED:
        if final.termination_reason is not TerminationReason.PLAYER_ENDED:
            raise SaveDataError(
                "ended run must use the player-ended termination reason"
            )
        if (
            final.termination_day != FINAL_DAY
            or final.termination_command_sequence is None
            or final.termination_command_sequence != state.command_sequence
        ):
            raise SaveDataError(
                "player-ended termination history is inconsistent"
            )
        if (
            not final.is_finalized
            or final.hard_fail_type is not None
            or final.ending_id not in _FINAL_ENDING_IDS - {"hard_fail"}
            or frost.final_score_day != FINAL_DAY
        ):
            raise SaveDataError(
                "player-ended run requires a completed survival result"
            )
    else:
        raise SaveDataError("unsupported final-result run state")

    report = final.report
    for name, values in (
        ("body_text_ids", report.body_text_ids),
        ("pending_text_ids", report.pending_text_ids),
        ("hidden_achievement_ids", report.hidden_achievement_ids),
        ("limiting_factor_ids", report.limiting_factor_ids),
    ):
        if len(values) != len(set(values)):
            raise SaveDataError(f"ending report {name} must be unique")
    if report.pending_text_ids != sorted(report.pending_text_ids):
        raise SaveDataError(
            "ending report pending text ids must use stable sorted order"
        )
    if report.hidden_achievement_ids != sorted(
        report.hidden_achievement_ids
    ):
        raise SaveDataError(
            "ending report hidden achievement ids must be sorted"
        )
    if report.limiting_factor_ids != sorted(report.limiting_factor_ids):
        raise SaveDataError(
            "ending report limiting factor ids must be sorted"
        )
    if not report.is_generated:
        if report != EndingReportState():
            raise SaveDataError(
                "ungenerated ending report cannot retain report fields"
            )
        if final.is_finalized:
            raise SaveDataError(
                "completed result must retain its generated ending report"
            )
    else:
        if (
            report.generated_day != state.calendar.current_day
            or not final.is_finalized
            or report.ending_state != final.ending_id
        ):
            raise SaveDataError(
                "ending report must match the completed result"
            )
        expected_display_result = (
            TerminationReason.PLAYER_ENDED.value
            if final.run_state is RunState.ENDED
            else final.ending_id
        )
        if report.display_result_id != expected_display_result:
            raise SaveDataError(
                "ending report presentation result is not canonical"
            )
        if final.run_state is RunState.ENDED:
            legacy_body_text_ids = list(ENDING_PLAYER_ENDED_BODY_TEXT_IDS)
        elif final.hard_fail_type is not None:
            legacy_body_text_ids = [
                ENDING_HARD_FAIL_REASON_TEXT_IDS[
                    final.hard_fail_type.value
                ]
            ]
        else:
            legacy_body_text_ids = []
        legacy_pending_text_ids = _expected_report_pending_text_ids(state)
        canonical_body_text_ids = canonical_report_body_text_ids(state)
        canonical_pending_text_ids = canonical_report_pending_text_ids(state)
        is_legacy_report = (
            report.title_text_id
            == ENDING_TITLE_TEXT_IDS[expected_display_result]
            and report.body_text_ids == legacy_body_text_ids
            and report.pending_text_ids == legacy_pending_text_ids
        )
        is_patch020_report = (
            report.title_text_id == canonical_report_title_text_id(state)
            and report.body_text_ids == canonical_body_text_ids
            and report.pending_text_ids == canonical_pending_text_ids
        )
        if not (is_legacy_report or is_patch020_report):
            raise SaveDataError(
                "ending report text selection is not canonical"
            )
        if report.hidden_achievement_ids != sorted(
            set(events.hidden_achievements_unlocked)
        ):
            raise SaveDataError(
                "ending report hidden achievements are inconsistent"
            )
        expected_limiting_factors = (
            ["wood_supply_locked"] if frost.wood_supply_locked else []
        )
        if report.limiting_factor_ids != expected_limiting_factors:
            raise SaveDataError(
                "ending report limiting factors are not canonical"
            )
        if (
            final.hard_fail_type is None
            and (
                report.generated_day != FINAL_DAY
                or state.calendar.current_day != FINAL_DAY
                or frost.final_score_day != FINAL_DAY
            )
        ):
            raise SaveDataError(
                "survival ending report requires a D55 score"
            )


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

    for facility in (
        state.oath_order.oath_hall,
        state.oath_order.patrol_office,
    ):
        assigned["workers"] += facility.assigned_workers
        assigned["engineers"] += facility.assigned_engineers

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
        restored = _decode_game_state(
            encode_game_state(state),
            None,
            strict_event_timeline=False,
        )
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
