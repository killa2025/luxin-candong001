from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file
from furnace_winter.config.status import ConfigStatus


class TechnologyConfigError(ValueError):
    pass


PATCH_006_TECH_IDS = frozenset(
    {
        "tech_advanced_housing_standard",
        "tech_automatic_forming_machine",
        "tech_building_insulation_1",
        "tech_building_insulation_2",
        "tech_canteen_process_improvement",
        "tech_coal_seam_support",
        "tech_deep_coal_seam_extraction",
        "tech_deep_steel_seam_extraction",
        "tech_deep_well_mine_frame",
        "tech_difference_engine",
        "tech_drafting_instrument",
        "tech_drawing_board",
        "tech_emergency_heating_device",
        "tech_field_cold_weather_equipment",
        "tech_final_furnace_stability",
        "tech_furnace_coal_saving_1",
        "tech_furnace_coal_saving_2",
        "tech_furnace_power_stability_1",
        "tech_greenhouse_cultivation",
        "tech_greenhouse_improvement",
        "tech_hospital_standardization",
        "tech_housing_insulation_1",
        "tech_hunting_equipment",
        "tech_improved_housing_standard",
        "tech_mechanical_calculator",
        "tech_medical_building_insulation",
        "tech_medical_tools_improvement",
        "tech_overload_stability",
        "tech_overload_tuning",
        "tech_scattered_gathering_tools",
        "tech_sheltered_gathering_shed_improvement",
        "tech_small_coal_mining_improvement",
        "tech_small_steel_mining_improvement",
        "tech_steel_screening",
        "tech_storage_expansion",
        "tech_wood_processing_1",
        "tech_wood_processing_2",
    }
)


@dataclass(frozen=True, slots=True)
class TechnologyRule:
    tech_id: str
    display_name: str
    tier: int
    wood_cost: int
    steel_cost: int
    research_days: int
    prerequisite_tech_ids: tuple[str, ...]
    effect_kind: str
    effect_targets: tuple[str, ...]
    effect_status: str


@dataclass(frozen=True, slots=True)
class ResearchRules:
    max_queues: int
    progress_units_per_day: int
    second_center_speed_numerator: int
    second_center_speed_denominator: int


@dataclass(frozen=True, slots=True)
class OverloadLevelRule:
    level: int
    temperature_bonus: int
    coal_cost: int
    pressure_growth: int
    stabilized_pressure_growth: int
    required_tech_id: str | None


@dataclass(frozen=True, slots=True)
class OverloadRules:
    levels: Mapping[int, OverloadLevelRule]
    active_cooling: int
    furnace_off_cooling: int
    high_pressure_threshold: int
    redline_threshold: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "levels", MappingProxyType(dict(self.levels)))


@dataclass(frozen=True, slots=True)
class TechnologyRules:
    schema_version: int
    config_status: ConfigStatus
    research: ResearchRules
    overload: OverloadRules
    technologies: Mapping[str, TechnologyRule]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "technologies", MappingProxyType(dict(self.technologies))
        )

    def tier_unlock_tech_id(self, tier: int) -> str | None:
        if tier == 0:
            return None
        target = f"T{tier}"
        matches = [
            rule.tech_id
            for rule in self.technologies.values()
            if rule.effect_kind == "unlock_tier" and target in rule.effect_targets
        ]
        if len(matches) != 1:
            raise TechnologyConfigError(
                f"tier {tier} must have exactly one unlock technology"
            )
        return matches[0]


def validate_technology_building_links(
    technology_rules: TechnologyRules,
    building_rules: Any,
) -> None:
    """Validate every Patch 006 building/upgrade/heat technology link both ways."""

    technologies = technology_rules.technologies
    known_tech_ids = set(technologies)
    for building_type, building in building_rules.buildings.items():
        for tech_id in building.required_tech_ids:
            if tech_id not in known_tech_ids:
                raise TechnologyConfigError(
                    f"building {building_type} references unknown technology {tech_id}"
                )
            rule = technologies[tech_id]
            if (
                rule.effect_kind != "unlock_building"
                or building_type not in rule.effect_targets
            ):
                raise TechnologyConfigError(
                    f"building {building_type} and technology {tech_id} disagree"
                )

    for upgrade_id, upgrade in building_rules.upgrades.items():
        tech_id = upgrade.required_tech_id
        if tech_id not in known_tech_ids:
            raise TechnologyConfigError(
                f"upgrade {upgrade_id} references unknown technology {tech_id}"
            )
        rule = technologies[tech_id]
        if rule.effect_kind != "unlock_upgrade" or upgrade_id not in rule.effect_targets:
            raise TechnologyConfigError(
                f"upgrade {upgrade_id} and technology {tech_id} disagree"
            )

    heat_tech_id = building_rules.heat.enhancement_tech_id
    if heat_tech_id not in known_tech_ids:
        raise TechnologyConfigError(
            f"heat references unknown technology {heat_tech_id}"
        )
    heat_rule = technologies[heat_tech_id]
    if heat_rule.effect_kind != "upgrade_command" or "game.heat" not in heat_rule.effect_targets:
        raise TechnologyConfigError(
            f"heat and technology {heat_tech_id} disagree"
        )

    for tech_id, rule in technologies.items():
        if rule.effect_kind == "unlock_building":
            for building_type in rule.effect_targets:
                building = building_rules.buildings.get(building_type)
                if building is None:
                    raise TechnologyConfigError(
                        f"technology {tech_id} references unknown building {building_type}"
                    )
                if tech_id not in building.required_tech_ids:
                    raise TechnologyConfigError(
                        f"technology {tech_id} and building {building_type} disagree"
                    )
        elif rule.effect_kind == "unlock_upgrade":
            for upgrade_id in rule.effect_targets:
                upgrade = building_rules.upgrades.get(upgrade_id)
                if upgrade is None:
                    raise TechnologyConfigError(
                        f"technology {tech_id} references unknown upgrade {upgrade_id}"
                    )
                if upgrade.required_tech_id != tech_id:
                    raise TechnologyConfigError(
                        f"technology {tech_id} and upgrade {upgrade_id} disagree"
                    )
        elif "game.heat" in rule.effect_targets and tech_id != heat_tech_id:
            raise TechnologyConfigError(
                f"technology {tech_id} conflicts with the configured heat technology"
            )


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TechnologyConfigError(f"{path} must be an object")
    return dict(value)


def _exact(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing or unknown:
        raise TechnologyConfigError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise TechnologyConfigError(f"{path} must be an integer >= {minimum}")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise TechnologyConfigError(f"{path} must be a normalized non-empty string")
    return value


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TechnologyConfigError(f"{path} must be an array")
    result = tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(set(result)) != len(result):
        raise TechnologyConfigError(f"{path} must not contain duplicates")
    return result


def load_technology_rules(path: Path) -> TechnologyRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact(
        data,
        {"schema_version", "config_status", "research", "overload", "technologies"},
        "$",
    )
    schema_version = _integer(data["schema_version"], "$.schema_version", minimum=1)
    if schema_version != 1:
        raise TechnologyConfigError("unsupported technology schema_version")

    research_data = _object(data["research"], "$.research")
    _exact(
        research_data,
        {
            "max_queues",
            "progress_units_per_day",
            "second_center_speed_numerator",
            "second_center_speed_denominator",
        },
        "$.research",
    )
    research = ResearchRules(
        max_queues=_integer(research_data["max_queues"], "$.research.max_queues", minimum=1),
        progress_units_per_day=_integer(
            research_data["progress_units_per_day"],
            "$.research.progress_units_per_day",
            minimum=1,
        ),
        second_center_speed_numerator=_integer(
            research_data["second_center_speed_numerator"],
            "$.research.second_center_speed_numerator",
            minimum=1,
        ),
        second_center_speed_denominator=_integer(
            research_data["second_center_speed_denominator"],
            "$.research.second_center_speed_denominator",
            minimum=1,
        ),
    )
    if research.max_queues != 1:
        raise TechnologyConfigError("V1 supports exactly one research queue")
    if (
        research.progress_units_per_day
        * research.second_center_speed_numerator
        % research.second_center_speed_denominator
    ):
        raise TechnologyConfigError("second-center research speed must use exact units")
    if (
        research.second_center_speed_numerator * 2
        != research.second_center_speed_denominator * 3
    ):
        raise TechnologyConfigError("second-center research speed must equal 1.50")

    overload_data = _object(data["overload"], "$.overload")
    _exact(
        overload_data,
        {
            "levels",
            "active_cooling",
            "furnace_off_cooling",
            "high_pressure_threshold",
            "redline_threshold",
        },
        "$.overload",
    )
    raw_levels = _object(overload_data["levels"], "$.overload.levels")
    if set(raw_levels) != {"0", "1", "2"}:
        raise TechnologyConfigError(
            "overload level keys must be exactly the canonical strings 0, 1, and 2"
        )
    levels: dict[int, OverloadLevelRule] = {}
    for raw_level, raw_rule in raw_levels.items():
        level = int(raw_level)
        item = _object(raw_rule, f"$.overload.levels.{raw_level}")
        _exact(
            item,
            {
                "temperature_bonus",
                "coal_cost",
                "pressure_growth",
                "stabilized_pressure_growth",
                "required_tech_id",
            },
            f"$.overload.levels.{raw_level}",
        )
        required = item["required_tech_id"]
        if required is not None:
            required = _string(required, f"$.overload.levels.{raw_level}.required_tech_id")
        levels[level] = OverloadLevelRule(
            level=level,
            temperature_bonus=_integer(item["temperature_bonus"], f"$.overload.levels.{raw_level}.temperature_bonus"),
            coal_cost=_integer(item["coal_cost"], f"$.overload.levels.{raw_level}.coal_cost"),
            pressure_growth=_integer(item["pressure_growth"], f"$.overload.levels.{raw_level}.pressure_growth"),
            stabilized_pressure_growth=_integer(
                item["stabilized_pressure_growth"],
                f"$.overload.levels.{raw_level}.stabilized_pressure_growth",
            ),
            required_tech_id=required,
        )
    if set(levels) != {0, 1, 2}:
        raise TechnologyConfigError("overload levels must be exactly 0, 1, and 2")
    zero_level = levels[0]
    if (
        zero_level.temperature_bonus != 0
        or zero_level.coal_cost != 0
        or zero_level.pressure_growth != 0
        or zero_level.stabilized_pressure_growth != 0
        or zero_level.required_tech_id is not None
    ):
        raise TechnologyConfigError("overload level 0 must have only zero effects")
    expected_unlocks = {
        1: "tech_overload_tuning",
        2: "tech_overload_stability",
    }
    for level, required_tech_id in expected_unlocks.items():
        rule = levels[level]
        if rule.required_tech_id != required_tech_id:
            raise TechnologyConfigError(
                f"overload level {level} must require {required_tech_id}"
            )
        if (
            rule.temperature_bonus <= 0
            or rule.coal_cost <= 0
            or rule.pressure_growth <= 0
            or rule.stabilized_pressure_growth <= 0
            or rule.stabilized_pressure_growth > rule.pressure_growth
        ):
            raise TechnologyConfigError(
                f"overload level {level} must have positive sealed effects"
            )
    overload = OverloadRules(
        levels=levels,
        active_cooling=_integer(overload_data["active_cooling"], "$.overload.active_cooling"),
        furnace_off_cooling=_integer(overload_data["furnace_off_cooling"], "$.overload.furnace_off_cooling"),
        high_pressure_threshold=_integer(overload_data["high_pressure_threshold"], "$.overload.high_pressure_threshold", minimum=1),
        redline_threshold=_integer(overload_data["redline_threshold"], "$.overload.redline_threshold", minimum=1),
    )
    if overload.high_pressure_threshold >= overload.redline_threshold:
        raise TechnologyConfigError("high-pressure threshold must be below redline")
    if overload.redline_threshold != 100:
        raise TechnologyConfigError("Patch 006 redline threshold must equal 100")

    raw_technologies = _object(data["technologies"], "$.technologies")
    technologies: dict[str, TechnologyRule] = {}
    rule_fields = {
        "display_name",
        "tier",
        "wood_cost",
        "steel_cost",
        "research_days",
        "prerequisite_tech_ids",
        "effect_kind",
        "effect_targets",
        "effect_status",
    }
    allowed_effect_kinds = {
        "unlock_tier",
        "passive",
        "upgrade_command",
        "unlock_command",
        "unlock_building",
        "unlock_upgrade",
        "deferred",
    }
    for tech_id, raw_rule in raw_technologies.items():
        normalized_id = _string(tech_id, "$.technologies key")
        item = _object(raw_rule, f"$.technologies.{normalized_id}")
        _exact(item, rule_fields, f"$.technologies.{normalized_id}")
        effect_kind = _string(item["effect_kind"], f"$.technologies.{normalized_id}.effect_kind")
        if effect_kind not in allowed_effect_kinds:
            raise TechnologyConfigError(f"unsupported effect_kind: {effect_kind}")
        effect_status = _string(item["effect_status"], f"$.technologies.{normalized_id}.effect_status")
        if effect_status not in {"ACTIVE", "DEFERRED"}:
            raise TechnologyConfigError(f"unsupported effect_status: {effect_status}")
        if (effect_kind == "deferred") != (effect_status == "DEFERRED"):
            raise TechnologyConfigError(
                "deferred effect kind and effect status must agree"
            )
        technologies[normalized_id] = TechnologyRule(
            tech_id=normalized_id,
            display_name=_string(item["display_name"], f"$.technologies.{normalized_id}.display_name"),
            tier=_integer(item["tier"], f"$.technologies.{normalized_id}.tier"),
            wood_cost=_integer(item["wood_cost"], f"$.technologies.{normalized_id}.wood_cost"),
            steel_cost=_integer(item["steel_cost"], f"$.technologies.{normalized_id}.steel_cost"),
            research_days=_integer(item["research_days"], f"$.technologies.{normalized_id}.research_days", minimum=1),
            prerequisite_tech_ids=_strings(item["prerequisite_tech_ids"], f"$.technologies.{normalized_id}.prerequisite_tech_ids"),
            effect_kind=effect_kind,
            effect_targets=_strings(item["effect_targets"], f"$.technologies.{normalized_id}.effect_targets"),
            effect_status=effect_status,
        )

    actual_tech_ids = set(technologies)
    if actual_tech_ids != PATCH_006_TECH_IDS:
        raise TechnologyConfigError(
            "Patch 006 technology catalog mismatch: "
            f"missing={sorted(PATCH_006_TECH_IDS - actual_tech_ids)}, "
            f"unknown={sorted(actual_tech_ids - PATCH_006_TECH_IDS)}"
        )
    display_names = [rule.display_name for rule in technologies.values()]
    if len(set(display_names)) != len(display_names):
        raise TechnologyConfigError("technology display names must be unique")

    for rule in technologies.values():
        if rule.tier > 5:
            raise TechnologyConfigError(f"{rule.tech_id} tier must be between T0 and T5")
        unknown = sorted(set(rule.prerequisite_tech_ids) - set(technologies))
        if unknown:
            raise TechnologyConfigError(f"{rule.tech_id} has unknown prerequisites: {unknown}")
        if rule.tech_id in rule.prerequisite_tech_ids:
            raise TechnologyConfigError(f"{rule.tech_id} cannot require itself")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(tech_id: str) -> None:
        if tech_id in visiting:
            raise TechnologyConfigError("technology prerequisites must be acyclic")
        if tech_id in visited:
            return
        visiting.add(tech_id)
        for prerequisite in technologies[tech_id].prerequisite_tech_ids:
            visit(prerequisite)
        visiting.remove(tech_id)
        visited.add(tech_id)

    for tech_id in technologies:
        visit(tech_id)
    for level in levels.values():
        if level.required_tech_id is not None and level.required_tech_id not in technologies:
            raise TechnologyConfigError(
                f"overload {level.level} references unknown technology"
            )

    rules = TechnologyRules(
        schema_version=schema_version,
        config_status=loaded.status,
        research=research,
        overload=overload,
        technologies=technologies,
    )
    for tier in range(1, 6):
        unlock_id = rules.tier_unlock_tech_id(tier)
        assert unlock_id is not None
        if technologies[unlock_id].tier != tier - 1:
            raise TechnologyConfigError(
                f"{unlock_id} must unlock the immediately following tier"
            )
    return rules
