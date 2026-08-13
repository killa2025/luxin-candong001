from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file
from furnace_winter.config.status import ConfigStatus


class FinalFrostConfigError(ValueError):
    pass


def _freeze_mapping(value: Mapping[Any, Any]) -> Mapping[Any, Any]:
    return MappingProxyType(
        {
            key: _freeze_mapping(item) if isinstance(item, Mapping) else item
            for key, item in value.items()
        }
    )


@dataclass(frozen=True, slots=True)
class FrostTemperatureRule:
    real: int
    display_label: str


@dataclass(frozen=True, slots=True)
class FinalFrostRules:
    schema_version: int
    config_status: ConfigStatus
    start_day: int
    end_day: int
    final_settlement_day: int
    temperatures: Mapping[int, FrostTemperatureRule]
    shutdown_building_types: frozenset[str]
    shutdown_surface_collection: bool
    damage: Mapping[str, int]
    hunger: Mapping[str, int]
    daily_thresholds: Mapping[str, int]
    preparation: Mapping[str, Any]
    scoring: Mapping[str, Any]
    tag_severity: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "temperatures", MappingProxyType(dict(self.temperatures))
        )
        object.__setattr__(self, "damage", MappingProxyType(dict(self.damage)))
        object.__setattr__(self, "hunger", MappingProxyType(dict(self.hunger)))
        object.__setattr__(
            self,
            "daily_thresholds",
            MappingProxyType(dict(self.daily_thresholds)),
        )
        object.__setattr__(
            self, "preparation", MappingProxyType(dict(self.preparation))
        )
        object.__setattr__(self, "scoring", _freeze_mapping(self.scoring))
        object.__setattr__(
            self, "tag_severity", MappingProxyType(dict(self.tag_severity))
        )

    def is_frost_day(self, day: int) -> bool:
        return self.start_day <= day <= self.end_day


_DAMAGE_FIELDS = {
    "minimum_exposure_level",
    "extra_exposure_level",
    "exposure_level_cap",
    "exposure_population_unit",
    "small_group_minimum",
    "untreated_sick_severe_divisor",
    "untreated_sick_severe_level_2_divisor",
    "untreated_sick_severe_level_3_divisor",
    "untreated_sick_severe_level_4_divisor",
    "frost_untreated_sick_extra_severe_divisor",
    "untreated_critical_death_divisor",
    "untreated_critical_extra_death_divisor",
    "untreated_critical_disability_divisor",
    "treated_sick_recovery_divisor",
    "treated_critical_recovery_divisor",
    "treated_critical_death_divisor",
    "hospital_treated_critical_death_divisor",
    "treated_sick_severe_divisor",
    "cold_disability_level_2_divisor",
    "cold_disability_level_3_divisor",
    "cold_disability_level_4_divisor",
    "homeless_cold_death_divisor",
    "housed_cold_death_divisor",
    "frost_extra_cold_death_divisor",
    "d1_cold_death_cap",
    "medical_buffer_per_prevented_disability",
    "natural_death_cap_base",
    "natural_death_cap_maximum",
    "natural_death_cap_population_baseline",
    "natural_death_cap_population_divisor",
}
_HUNGER_FIELDS = {
    "illness_divisor",
    "severe_divisor",
    "death_divisor",
    "trust_divisor",
    "trust_daily_cap",
    "panic_divisor",
    "panic_daily_cap",
    "score_hunger_days_three_max",
    "score_hunger_days_two_max",
    "score_hunger_days_one_max",
    "score_peak_three_percent",
    "score_peak_two_percent",
    "score_peak_one_percent",
    "score_cumulative_three_percent",
    "score_cumulative_two_percent",
    "score_cumulative_one_percent",
    "score_frost_death_cap",
}
_DAILY_THRESHOLD_FIELDS = {
    "overload_redline",
    "core_near_collapse",
    "cold_houses_population_percent",
    "mass_cold_exposure_percent",
    "medical_overflow_gap",
    "medical_collapse_gap",
    "disease_spike_minimum",
    "disease_spike_population_percent",
    "mass_death_minimum",
    "mass_death_population_percent",
    "trust_crisis",
    "panic_crisis",
}
_PREPARATION_FIELDS = {
    "prepared_required_items",
    "prepared_coal_days",
    "prepared_food_days",
    "prepared_trust",
    "prepared_panic",
    "unprepared_required_items",
    "unprepared_coal_days",
    "unprepared_food_days",
    "unprepared_trust",
    "unprepared_panic",
    "unprepared_pressure",
    "key_technology_ids",
}
_SCORING_FIELDS = {
    "result_score_minimums",
    "high_victory_death_ratio_percent",
    "grave_city_death_ratio_percent",
    "mass_death_frost_ratio_percent",
    "city_continuity_minimum",
    "city_continuity_population_percent",
}
_RESULT_IDS = {
    "high_victory",
    "standard_victory",
    "bitter_victory",
    "collapse_survival",
    "ember_survival",
}
_TAG_SEVERITIES = {"major", "defining"}
_EXPECTED_KEY_TECHNOLOGY_IDS = {
    "tech_furnace_coal_saving_2",
    "tech_building_insulation_2",
    "tech_final_furnace_stability",
}
_EXPECTED_TAG_SEVERITY = {
    "coal_desperate": "major",
    "cold_engine": "major",
    "redline_survivor": "major",
    "famine_survivor": "major",
    "famine_city": "defining",
    "cold_houses": "major",
    "frozen_homeless": "defining",
    "medical_collapse": "major",
    "silent_hospital": "defining",
    "mass_death": "major",
    "grave_city": "defining",
    "broken_society": "major",
    "oath_carried_zero_trust": "defining",
    "decree_carried_panic": "defining",
    "city_continuity_broken": "major",
    "prepared_for_frost": "major",
    "unprepared_frost": "major",
    "frost_survived_clean": "major",
    "frost_survived_broken": "defining",
    "old_city_stabilized": "major",
    "old_city_persuaded": "major",
    "old_city_suppressed": "major",
    "old_city_departed": "defining",
    "old_city_unresolved": "major",
    "refugee_pressure": "major",
    "opened_gates": "major",
    "closed_gates": "major",
    "mourning_bell": "major",
    "ember_register": "major",
    "shared_meal_oath": "major",
    "stay_oath": "major",
    "final_oath": "defining",
    "morning_rollcall": "major",
    "unified_notice": "major",
    "detention_used": "major",
    "census_control": "major",
    "final_decree": "defining",
    "promise_keeper": "major",
    "promise_breaker": "major",
    "medical_promise_failed": "major",
    "food_promise_failed": "major",
    "children_promise_failed": "major",
    "old_city_promise_failed": "defining",
    "wood_supply_locked": "defining",
}


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FinalFrostConfigError(f"{path} must be an object")
    return dict(value)


def _exact(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing or unknown:
        raise FinalFrostConfigError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )


def _integer(
    value: Any, path: str, *, minimum: int | None = None
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise FinalFrostConfigError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise FinalFrostConfigError(f"{path} must be at least {minimum}")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise FinalFrostConfigError(f"{path} must be a boolean")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise FinalFrostConfigError(f"{path} must be a normalized string")
    return value


def _positive_integer_object(
    value: Any, expected: set[str], path: str
) -> dict[str, int]:
    data = _object(value, path)
    _exact(data, expected, path)
    return {
        key: _integer(data[key], f"{path}.{key}", minimum=1)
        for key in expected
    }


def load_final_frost_rules(path: Path) -> FinalFrostRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact(
        data,
        {
            "schema_version",
            "config_status",
            "calendar",
            "restrictions",
            "damage",
            "hunger",
            "daily_thresholds",
            "preparation",
            "scoring",
            "tag_severity",
        },
        "$",
    )
    schema_version = _integer(
        data["schema_version"], "$.schema_version", minimum=1
    )
    if schema_version != 1:
        raise FinalFrostConfigError(
            "unsupported final-frost schema_version"
        )
    if loaded.status is not ConfigStatus.TEST_NUMERIC:
        raise FinalFrostConfigError(
            "Patch 009 provisional values must remain TEST_NUMERIC"
        )

    calendar = _object(data["calendar"], "$.calendar")
    _exact(
        calendar,
        {"start_day", "end_day", "final_settlement_day", "temperatures"},
        "$.calendar",
    )
    start_day = _integer(calendar["start_day"], "$.calendar.start_day")
    end_day = _integer(calendar["end_day"], "$.calendar.end_day")
    final_day = _integer(
        calendar["final_settlement_day"],
        "$.calendar.final_settlement_day",
    )
    if (start_day, end_day, final_day) != (49, 55, 55):
        raise FinalFrostConfigError(
            "the sealed final-frost calendar must remain 49/55/55"
        )
    raw_temperatures = _object(
        calendar["temperatures"], "$.calendar.temperatures"
    )
    expected_days = {str(day) for day in range(start_day, end_day + 1)}
    _exact(raw_temperatures, expected_days, "$.calendar.temperatures")
    temperatures: dict[int, FrostTemperatureRule] = {}
    for raw_day, raw_value in raw_temperatures.items():
        value = _object(
            raw_value, f"$.calendar.temperatures.{raw_day}"
        )
        _exact(
            value,
            {"real", "display_label"},
            f"$.calendar.temperatures.{raw_day}",
        )
        temperatures[int(raw_day)] = FrostTemperatureRule(
            real=_integer(
                value["real"],
                f"$.calendar.temperatures.{raw_day}.real",
            ),
            display_label=_string(
                value["display_label"],
                f"$.calendar.temperatures.{raw_day}.display_label",
            ),
        )
    expected_real = {
        49: -66,
        50: -68,
        51: -70,
        52: -66,
        53: -72,
        54: -74,
        55: -76,
    }
    if {
        day: rule.real for day, rule in temperatures.items()
    } != expected_real:
        raise FinalFrostConfigError(
            "the sealed D49-D55 real temperatures changed"
        )
    expected_labels = {
        **{day: "-70级第七霜落" for day in range(49, 55)},
        55: "-80级第七霜落",
    }
    if {
        day: rule.display_label for day, rule in temperatures.items()
    } != expected_labels:
        raise FinalFrostConfigError(
            "the sealed D49-D55 display labels changed"
        )

    restrictions = _object(data["restrictions"], "$.restrictions")
    _exact(
        restrictions,
        {"shutdown_building_types", "shutdown_surface_collection"},
        "$.restrictions",
    )
    raw_shutdown = restrictions["shutdown_building_types"]
    if not isinstance(raw_shutdown, list):
        raise FinalFrostConfigError(
            "$.restrictions.shutdown_building_types must be an array"
        )
    shutdown = frozenset(
        _string(
            item,
            f"$.restrictions.shutdown_building_types[{index}]",
        )
        for index, item in enumerate(raw_shutdown)
    )
    if len(shutdown) != len(raw_shutdown):
        raise FinalFrostConfigError(
            "shutdown building types must be unique"
        )
    expected_shutdown = {
        "hunting_lodge",
        "logging_camp",
        "small_coal_miner",
        "small_steel_miner",
    }
    if shutdown != expected_shutdown:
        raise FinalFrostConfigError(
            "the sealed final-frost shutdown catalog changed"
        )
    if restrictions["shutdown_surface_collection"] is not True:
        raise FinalFrostConfigError(
            "final frost must shut down surface collection"
        )

    damage = _positive_integer_object(
        data["damage"], _DAMAGE_FIELDS, "$.damage"
    )
    confirmed_damage_values = {
        "untreated_sick_severe_divisor": 6,
        "untreated_sick_severe_level_2_divisor": 5,
        "untreated_sick_severe_level_3_divisor": 4,
        "untreated_sick_severe_level_4_divisor": 3,
        "frost_untreated_sick_extra_severe_divisor": 6,
        "natural_death_cap_base": 12,
        "natural_death_cap_maximum": 22,
        "natural_death_cap_population_baseline": 80,
        "natural_death_cap_population_divisor": 35,
        "d1_cold_death_cap": 1,
    }
    if any(
        damage[name] != expected
        for name, expected in confirmed_damage_values.items()
    ):
        raise FinalFrostConfigError(
            "confirmed final-frost disease and natural-death formulas changed"
        )
    daily_thresholds = _positive_integer_object(
        data["daily_thresholds"],
        _DAILY_THRESHOLD_FIELDS,
        "$.daily_thresholds",
    )
    hunger = _positive_integer_object(
        data["hunger"], _HUNGER_FIELDS, "$.hunger"
    )
    if hunger != {
        "illness_divisor": 5,
        "severe_divisor": 6,
        "death_divisor": 8,
        "trust_divisor": 20,
        "trust_daily_cap": 6,
        "panic_divisor": 15,
        "panic_daily_cap": 8,
        "score_hunger_days_three_max": 1,
        "score_hunger_days_two_max": 2,
        "score_hunger_days_one_max": 4,
        "score_peak_three_percent": 10,
        "score_peak_two_percent": 25,
        "score_peak_one_percent": 50,
        "score_cumulative_three_percent": 5,
        "score_cumulative_two_percent": 15,
        "score_cumulative_one_percent": 30,
        "score_frost_death_cap": 1,
    }:
        raise FinalFrostConfigError(
            "the confirmed Patch 013 hunger progression changed"
        )

    preparation = _object(data["preparation"], "$.preparation")
    _exact(preparation, _PREPARATION_FIELDS, "$.preparation")
    key_techs = preparation["key_technology_ids"]
    if not isinstance(key_techs, list):
        raise FinalFrostConfigError(
            "$.preparation.key_technology_ids must be an array"
        )
    normalized_preparation: dict[str, Any] = {
        key: _integer(preparation[key], f"$.preparation.{key}", minimum=1)
        for key in _PREPARATION_FIELDS - {"key_technology_ids"}
    }
    normalized_preparation["key_technology_ids"] = tuple(
        _string(item, f"$.preparation.key_technology_ids[{index}]")
        for index, item in enumerate(key_techs)
    )
    if len(set(normalized_preparation["key_technology_ids"])) != len(
        normalized_preparation["key_technology_ids"]
    ):
        raise FinalFrostConfigError(
            "preparation technology ids must be unique"
        )
    if set(normalized_preparation["key_technology_ids"]) != (
        _EXPECTED_KEY_TECHNOLOGY_IDS
    ):
        raise FinalFrostConfigError(
            "the final-frost key technology catalog changed"
        )
    expected_preparation = {
        "prepared_required_items": 6,
        "prepared_coal_days": 6,
        "prepared_food_days": 6,
        "prepared_trust": 55,
        "prepared_panic": 45,
        "unprepared_required_items": 3,
        "unprepared_coal_days": 3,
        "unprepared_food_days": 3,
        "unprepared_trust": 40,
        "unprepared_panic": 65,
        "unprepared_pressure": 80,
    }
    if any(
        normalized_preparation[name] != expected
        for name, expected in expected_preparation.items()
    ):
        raise FinalFrostConfigError(
            "the Patch 022 preparation thresholds changed"
        )

    scoring = _object(data["scoring"], "$.scoring")
    _exact(scoring, _SCORING_FIELDS, "$.scoring")
    result_mins = _object(
        scoring["result_score_minimums"],
        "$.scoring.result_score_minimums",
    )
    _exact(
        result_mins,
        _RESULT_IDS,
        "$.scoring.result_score_minimums",
    )
    normalized_scoring: dict[str, Any] = {
        key: _integer(scoring[key], f"$.scoring.{key}", minimum=1)
        for key in _SCORING_FIELDS - {"result_score_minimums"}
    }
    normalized_scoring["result_score_minimums"] = {
        key: _integer(
            result_mins[key],
            f"$.scoring.result_score_minimums.{key}",
            minimum=0,
        )
        for key in _RESULT_IDS
    }
    if normalized_scoring["result_score_minimums"] != {
        "high_victory": 22,
        "standard_victory": 18,
        "bitter_victory": 12,
        "collapse_survival": 7,
        "ember_survival": 0,
    }:
        raise FinalFrostConfigError(
            "the Patch 022 result score bands changed"
        )
    if normalized_scoring["high_victory_death_ratio_percent"] != 5:
        raise FinalFrostConfigError(
            "the Patch 022 high-victory death threshold changed"
        )
    if normalized_scoring["grave_city_death_ratio_percent"] != 30:
        raise FinalFrostConfigError(
            "grave_city must use the confirmed strict 30 percent threshold"
        )

    raw_severity = _object(data["tag_severity"], "$.tag_severity")
    severity = {
        _string(key, "$.tag_severity key"): _string(
            value, f"$.tag_severity.{key}"
        )
        for key, value in raw_severity.items()
    }
    if not severity or set(severity.values()) - _TAG_SEVERITIES:
        raise FinalFrostConfigError(
            "tag severity values must be major or defining"
        )
    if severity != _EXPECTED_TAG_SEVERITY:
        raise FinalFrostConfigError(
            "the required final-frost tag severity catalog changed"
        )

    return FinalFrostRules(
        schema_version=schema_version,
        config_status=loaded.status,
        start_day=start_day,
        end_day=end_day,
        final_settlement_day=final_day,
        temperatures=temperatures,
        shutdown_building_types=shutdown,
        shutdown_surface_collection=_boolean(
            restrictions["shutdown_surface_collection"],
            "$.restrictions.shutdown_surface_collection",
        ),
        damage=damage,
        hunger=hunger,
        daily_thresholds=daily_thresholds,
        preparation=normalized_preparation,
        scoring=normalized_scoring,
        tag_severity=severity,
    )
