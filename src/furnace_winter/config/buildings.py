from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file


class BuildingConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BuildingRule:
    building_type: str
    display_name: str
    buildable: bool
    wood_cost: int
    steel_cost: int
    slot_size: int
    allowed_zones: tuple[str, ...]
    max_buildings: int | None
    max_count_source: str
    required_law_ids: tuple[str, ...]
    required_tech_ids: tuple[str, ...]
    staff_capacity: int
    allowed_staff_types: tuple[str, ...]
    housing_capacity: int
    storage_capacity_add: int
    output_resource: str | None
    output_per_day: int
    raw_food_processing_cap: int
    min_operating_temperature: int | None
    can_heat: bool
    binding_kind: str | None


@dataclass(frozen=True, slots=True)
class UpgradeRule:
    upgrade_id: str
    from_type: str
    to_type: str
    required_tech_id: str
    wood_cost: int
    steel_cost: int


@dataclass(frozen=True, slots=True)
class SurfaceResourcePointRule:
    resource_point_id: str
    resource_type: str
    total_amount: int
    staff_capacity: int
    output_per_day: int


@dataclass(frozen=True, slots=True)
class HeatRule:
    coal_cost: int
    temperature_bonus: int
    enhanced_temperature_bonus: int
    enhancement_tech_id: str
    daily_city_limit: int


@dataclass(frozen=True, slots=True)
class WoodfuelRule:
    wood_per_fuel: int
    daily_wood_limit: int
    minimum_wood_unit: int
    cooldown_days: int


@dataclass(frozen=True, slots=True)
class BuildingRules:
    zone_slot_capacity: Mapping[str, int]
    resource_anchors: Mapping[str, tuple[str, ...]]
    surface_resource_points: Mapping[str, SurfaceResourcePointRule]
    buildings: Mapping[str, BuildingRule]
    upgrades: Mapping[str, UpgradeRule]
    heat: HeatRule
    woodfuel: WoodfuelRule

    def __post_init__(self) -> None:
        object.__setattr__(self, "zone_slot_capacity", MappingProxyType(dict(self.zone_slot_capacity)))
        object.__setattr__(self, "resource_anchors", MappingProxyType(dict(self.resource_anchors)))
        object.__setattr__(
            self,
            "surface_resource_points",
            MappingProxyType(dict(self.surface_resource_points)),
        )
        object.__setattr__(self, "buildings", MappingProxyType(dict(self.buildings)))
        object.__setattr__(self, "upgrades", MappingProxyType(dict(self.upgrades)))


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BuildingConfigError(f"{path} must be an object")
    return dict(value)


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise BuildingConfigError(f"{path} must be an integer of at least {minimum}")
    return value


def _string(value: Any, path: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise BuildingConfigError(f"{path} must be a normalized non-empty string")
    return value


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise BuildingConfigError(f"{path} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        checked = _string(item, f"{path}[{index}]")
        assert isinstance(checked, str)
        result.append(checked)
    if len(result) != len(set(result)):
        raise BuildingConfigError(f"{path} must not contain duplicates")
    return tuple(result)


def _exact(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing or unknown:
        raise BuildingConfigError(
            f"{path} keys do not match schema; missing={missing}, unknown={unknown}"
        )


_BUILDING_KEYS = {
    "display_name", "buildable", "wood_cost", "steel_cost", "slot_size", "allowed_zones",
    "max_buildings", "max_count_source", "required_law_ids", "required_tech_ids",
    "staff_capacity", "allowed_staff_types", "housing_capacity",
    "storage_capacity_add", "output_resource", "output_per_day",
    "raw_food_processing_cap", "min_operating_temperature", "can_heat",
    "binding_kind",
}

_RESOURCE_TYPES = {"coal", "wood", "steel", "raw_food", "cooked_food"}
_STAFF_TYPES = {
    "workers",
    "engineers",
    "children",
    "medical_apprentices",
    "engineering_apprentices",
}
_SURFACE_RESOURCE_POINT_KEYS = {
    "resource_type",
    "total_amount",
    "staff_capacity",
    "output_per_day",
}


def load_building_rules(path: Path) -> BuildingRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact(
        data,
        {
            "schema_version", "config_status", "zone_slot_capacity",
            "resource_anchors", "surface_resource_points", "buildings",
            "upgrades", "heat", "woodfuel",
        },
        "$",
    )
    if _integer(data["schema_version"], "$.schema_version", minimum=1) != 2:
        raise BuildingConfigError("unsupported building schema_version")

    raw_zones = _object(data["zone_slot_capacity"], "$.zone_slot_capacity")
    zones = {
        key: _integer(value, f"$.zone_slot_capacity.{key}", minimum=1)
        for key, value in raw_zones.items()
    }
    if set(zones) != {"inner_ring", "middle_ring", "outer_ring", "storage_outer"}:
        raise BuildingConfigError("zone_slot_capacity must use the four official regions")

    raw_anchors = _object(data["resource_anchors"], "$.resource_anchors")
    anchors = {key: _strings(value, f"$.resource_anchors.{key}") for key, value in raw_anchors.items()}
    if set(anchors) != {"surface_resource_point", "forest_zone", "hunting_area"}:
        raise BuildingConfigError("resource_anchors must define surface, forest, and hunting areas")
    all_anchor_ids = [anchor_id for values in anchors.values() for anchor_id in values]
    if len(all_anchor_ids) != len(set(all_anchor_ids)):
        raise BuildingConfigError("resource anchor ids must be globally unique")

    raw_points = _object(data["surface_resource_points"], "$.surface_resource_points")
    surface_resource_points: dict[str, SurfaceResourcePointRule] = {}
    for resource_point_id, raw_value in raw_points.items():
        checked_id = _string(resource_point_id, "$.surface_resource_points key")
        assert isinstance(checked_id, str)
        item = _object(raw_value, f"$.surface_resource_points.{checked_id}")
        _exact(item, _SURFACE_RESOURCE_POINT_KEYS, f"$.surface_resource_points.{checked_id}")
        resource_type = _string(
            item["resource_type"],
            f"$.surface_resource_points.{checked_id}.resource_type",
        )
        assert isinstance(resource_type, str)
        if resource_type not in {"coal", "wood", "steel"}:
            raise BuildingConfigError(
                f"$.surface_resource_points.{checked_id}.resource_type is unsupported"
            )
        surface_resource_points[checked_id] = SurfaceResourcePointRule(
            resource_point_id=checked_id,
            resource_type=resource_type,
            total_amount=_integer(
                item["total_amount"],
                f"$.surface_resource_points.{checked_id}.total_amount",
                minimum=1,
            ),
            staff_capacity=_integer(
                item["staff_capacity"],
                f"$.surface_resource_points.{checked_id}.staff_capacity",
                minimum=1,
            ),
            output_per_day=_integer(
                item["output_per_day"],
                f"$.surface_resource_points.{checked_id}.output_per_day",
                minimum=1,
            ),
        )
    if set(surface_resource_points) != set(anchors["surface_resource_point"]):
        raise BuildingConfigError(
            "surface_resource_points must exactly match surface_resource_point anchors"
        )

    raw_buildings = _object(data["buildings"], "$.buildings")
    buildings: dict[str, BuildingRule] = {}
    for building_type, raw_value in raw_buildings.items():
        checked_type = _string(building_type, "$.buildings key")
        assert isinstance(checked_type, str)
        item = _object(raw_value, f"$.buildings.{building_type}")
        _exact(item, _BUILDING_KEYS, f"$.buildings.{building_type}")
        max_buildings_raw = item["max_buildings"]
        max_buildings = None if max_buildings_raw is None else _integer(
            max_buildings_raw, f"$.buildings.{building_type}.max_buildings", minimum=1
        )
        output_resource = _string(
            item["output_resource"], f"$.buildings.{building_type}.output_resource", optional=True
        )
        if output_resource is not None and output_resource not in _RESOURCE_TYPES:
            raise BuildingConfigError(
                f"$.buildings.{building_type}.output_resource is unsupported"
            )
        minimum_temperature = item["min_operating_temperature"]
        if minimum_temperature is not None and (
            not isinstance(minimum_temperature, int) or isinstance(minimum_temperature, bool)
        ):
            raise BuildingConfigError(
                f"$.buildings.{building_type}.min_operating_temperature must be an integer or null"
            )
        can_heat = item["can_heat"]
        if not isinstance(can_heat, bool):
            raise BuildingConfigError(f"$.buildings.{building_type}.can_heat must be a boolean")
        buildable = item["buildable"]
        if not isinstance(buildable, bool):
            raise BuildingConfigError(f"$.buildings.{building_type}.buildable must be a boolean")
        allowed_zones = _strings(item["allowed_zones"], f"$.buildings.{building_type}.allowed_zones")
        if not allowed_zones or not set(allowed_zones) <= set(zones):
            raise BuildingConfigError(f"$.buildings.{building_type}.allowed_zones is invalid")
        max_count_source = _string(item["max_count_source"], f"$.buildings.{building_type}.max_count_source")
        assert isinstance(max_count_source, str)
        if max_count_source not in {"fixed", "hunting_areas", "forest_zones"}:
            raise BuildingConfigError(f"unsupported max_count_source: {max_count_source}")
        binding_kind = _string(item["binding_kind"], f"$.buildings.{building_type}.binding_kind", optional=True)
        if binding_kind is not None and binding_kind not in anchors:
            raise BuildingConfigError(f"unknown binding_kind: {binding_kind}")
        staff_capacity = _integer(
            item["staff_capacity"], f"$.buildings.{building_type}.staff_capacity"
        )
        allowed_staff_types = _strings(
            item["allowed_staff_types"],
            f"$.buildings.{building_type}.allowed_staff_types",
        )
        if not set(allowed_staff_types) <= _STAFF_TYPES:
            raise BuildingConfigError(
                f"$.buildings.{building_type}.allowed_staff_types contains an unknown type"
            )
        if (staff_capacity == 0) != (not allowed_staff_types):
            raise BuildingConfigError(
                f"$.buildings.{building_type} staff capacity and allowed types disagree"
            )
        output_per_day = _integer(
            item["output_per_day"], f"$.buildings.{building_type}.output_per_day"
        )
        raw_food_processing_cap = _integer(
            item["raw_food_processing_cap"],
            f"$.buildings.{building_type}.raw_food_processing_cap",
        )
        if output_per_day > 0 and (output_resource is None or staff_capacity == 0):
            raise BuildingConfigError(
                f"$.buildings.{building_type} output requires a resource and staffed capacity"
            )
        if raw_food_processing_cap > 0 and staff_capacity == 0:
            raise BuildingConfigError(
                f"$.buildings.{building_type} processing requires staffed capacity"
            )
        if can_heat and minimum_temperature is None:
            raise BuildingConfigError(
                f"$.buildings.{building_type} heat requires an operating temperature threshold"
            )
        buildings[checked_type] = BuildingRule(
            building_type=checked_type,
            display_name=str(_string(item["display_name"], f"$.buildings.{building_type}.display_name")),
            buildable=buildable,
            wood_cost=_integer(item["wood_cost"], f"$.buildings.{building_type}.wood_cost"),
            steel_cost=_integer(item["steel_cost"], f"$.buildings.{building_type}.steel_cost"),
            slot_size=_integer(item["slot_size"], f"$.buildings.{building_type}.slot_size"),
            allowed_zones=allowed_zones,
            max_buildings=max_buildings,
            max_count_source=max_count_source,
            required_law_ids=_strings(item["required_law_ids"], f"$.buildings.{building_type}.required_law_ids"),
            required_tech_ids=_strings(item["required_tech_ids"], f"$.buildings.{building_type}.required_tech_ids"),
            staff_capacity=staff_capacity,
            allowed_staff_types=allowed_staff_types,
            housing_capacity=_integer(item["housing_capacity"], f"$.buildings.{building_type}.housing_capacity"),
            storage_capacity_add=_integer(item["storage_capacity_add"], f"$.buildings.{building_type}.storage_capacity_add"),
            output_resource=output_resource,
            output_per_day=output_per_day,
            raw_food_processing_cap=raw_food_processing_cap,
            min_operating_temperature=minimum_temperature,
            can_heat=can_heat,
            binding_kind=binding_kind,
        )

    raw_upgrades = _object(data["upgrades"], "$.upgrades")
    upgrades: dict[str, UpgradeRule] = {}
    upgrade_keys = {"from_type", "to_type", "required_tech_id", "wood_cost", "steel_cost"}
    for upgrade_id, raw_value in raw_upgrades.items():
        item = _object(raw_value, f"$.upgrades.{upgrade_id}")
        _exact(item, upgrade_keys, f"$.upgrades.{upgrade_id}")
        from_type = str(_string(item["from_type"], f"$.upgrades.{upgrade_id}.from_type"))
        to_type = str(_string(item["to_type"], f"$.upgrades.{upgrade_id}.to_type"))
        if from_type not in buildings or to_type not in buildings:
            raise BuildingConfigError(f"$.upgrades.{upgrade_id} references an unknown building")
        if buildings[from_type].slot_size != buildings[to_type].slot_size:
            raise BuildingConfigError(
                f"$.upgrades.{upgrade_id} cannot change slot_size in Patch 004"
            )
        upgrades[upgrade_id] = UpgradeRule(
            upgrade_id=upgrade_id,
            from_type=from_type,
            to_type=to_type,
            required_tech_id=str(_string(item["required_tech_id"], f"$.upgrades.{upgrade_id}.required_tech_id")),
            wood_cost=_integer(item["wood_cost"], f"$.upgrades.{upgrade_id}.wood_cost"),
            steel_cost=_integer(item["steel_cost"], f"$.upgrades.{upgrade_id}.steel_cost"),
        )

    heat_data = _object(data["heat"], "$.heat")
    _exact(heat_data, {"coal_cost", "temperature_bonus", "enhanced_temperature_bonus", "enhancement_tech_id", "daily_city_limit"}, "$.heat")
    woodfuel_data = _object(data["woodfuel"], "$.woodfuel")
    _exact(woodfuel_data, {"wood_per_fuel", "daily_wood_limit", "minimum_wood_unit", "cooldown_days"}, "$.woodfuel")
    heat_bonus = _integer(heat_data["temperature_bonus"], "$.heat.temperature_bonus", minimum=1)
    enhanced_heat_bonus = _integer(
        heat_data["enhanced_temperature_bonus"],
        "$.heat.enhanced_temperature_bonus",
        minimum=1,
    )
    if enhanced_heat_bonus < heat_bonus:
        raise BuildingConfigError("$.heat.enhanced_temperature_bonus cannot be lower than base")
    wood_per_fuel = _integer(
        woodfuel_data["wood_per_fuel"], "$.woodfuel.wood_per_fuel", minimum=1
    )
    daily_wood_limit = _integer(
        woodfuel_data["daily_wood_limit"], "$.woodfuel.daily_wood_limit", minimum=1
    )
    minimum_wood_unit = _integer(
        woodfuel_data["minimum_wood_unit"], "$.woodfuel.minimum_wood_unit", minimum=1
    )
    if minimum_wood_unit % wood_per_fuel or daily_wood_limit % minimum_wood_unit:
        raise BuildingConfigError(
            "woodfuel units must divide evenly into the minimum and daily limit"
        )
    return BuildingRules(
        zone_slot_capacity=zones,
        resource_anchors=anchors,
        surface_resource_points=surface_resource_points,
        buildings=buildings,
        upgrades=upgrades,
        heat=HeatRule(
            coal_cost=_integer(heat_data["coal_cost"], "$.heat.coal_cost", minimum=1),
            temperature_bonus=heat_bonus,
            enhanced_temperature_bonus=enhanced_heat_bonus,
            enhancement_tech_id=str(_string(heat_data["enhancement_tech_id"], "$.heat.enhancement_tech_id")),
            daily_city_limit=_integer(
                heat_data["daily_city_limit"], "$.heat.daily_city_limit", minimum=1
            ),
        ),
        woodfuel=WoodfuelRule(
            wood_per_fuel=wood_per_fuel,
            daily_wood_limit=daily_wood_limit,
            minimum_wood_unit=minimum_wood_unit,
            cooldown_days=_integer(woodfuel_data["cooldown_days"], "$.woodfuel.cooldown_days"),
        ),
    )
