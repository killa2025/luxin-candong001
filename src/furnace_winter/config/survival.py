from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file


class SurvivalConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FurnaceLevelRule:
    coal_cost: int
    heating: int


@dataclass(frozen=True, slots=True)
class StartingPopulationRules:
    workers: int
    engineers: int
    children: int

    @property
    def total(self) -> int:
        return self.workers + self.engineers + self.children


@dataclass(frozen=True, slots=True)
class StartingResourceRules:
    coal: int
    wood: int
    steel: int
    raw_food: int
    cooked_food: int
    storage_capacity: int


@dataclass(frozen=True, slots=True)
class SurvivalRules:
    population: StartingPopulationRules
    resources: StartingResourceRules
    basic_residences: int
    basic_residence_capacity: int
    starting_furnace_level: int
    starting_trust: int
    starting_panic: int
    food_per_person: int
    raw_to_cooked_ratio: int
    furnace_levels: Mapping[int, FurnaceLevelRule]
    weather_temperatures: tuple[int, ...]
    zone_modifiers: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "furnace_levels",
            MappingProxyType(dict(self.furnace_levels)),
        )
        object.__setattr__(
            self,
            "zone_modifiers",
            MappingProxyType(dict(self.zone_modifiers)),
        )
        expected_levels = {0, 1, 2, 3}
        if set(self.furnace_levels) != expected_levels:
            raise SurvivalConfigError("furnace levels must be exactly 0, 1, 2, and 3")
        if self.furnace_levels[0] != FurnaceLevelRule(coal_cost=0, heating=0):
            raise SurvivalConfigError("furnace level 0 must cost 0 coal and provide 0 heat")
        for level in range(1, 4):
            previous = self.furnace_levels[level - 1]
            current = self.furnace_levels[level]
            if current.coal_cost <= previous.coal_cost:
                raise SurvivalConfigError("furnace coal costs must increase by level")
            if current.heating <= previous.heating:
                raise SurvivalConfigError("furnace heating must increase by level")
        if len(self.weather_temperatures) != 55:
            raise SurvivalConfigError("weather table must contain exactly 55 days")
        if set(self.zone_modifiers) != {"inner_ring", "middle_ring", "outer_ring"}:
            raise SurvivalConfigError("zone modifiers must use the three official regions")
        for name, value in (
            ("population total", self.population.total),
            ("basic residences", self.basic_residences),
            ("basic residence capacity", self.basic_residence_capacity),
            ("food per person", self.food_per_person),
            ("raw to cooked ratio", self.raw_to_cooked_ratio),
        ):
            if value <= 0:
                raise SurvivalConfigError(f"{name} must be positive")
        if self.starting_furnace_level not in expected_levels:
            raise SurvivalConfigError("starting furnace level must be between 0 and 3")
        for name, value in (
            ("starting trust", self.starting_trust),
            ("starting panic", self.starting_panic),
        ):
            if not 0 <= value <= 100:
                raise SurvivalConfigError(f"{name} must be between 0 and 100")

    @property
    def starting_housing_capacity(self) -> int:
        return self.basic_residences * self.basic_residence_capacity

    def weather_for_day(self, day: int) -> int:
        if not 1 <= day <= len(self.weather_temperatures):
            raise ValueError("day is outside the fixed weather table")
        return self.weather_temperatures[day - 1]


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SurvivalConfigError(f"{path} must be an object")
    return dict(value)


def _integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SurvivalConfigError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise SurvivalConfigError(f"{path} must be at least {minimum}")
    return value


def _exact_keys(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing or unknown:
        raise SurvivalConfigError(
            f"{path} keys do not match schema; missing={missing}, unknown={unknown}"
        )


def load_survival_rules(path: Path) -> SurvivalRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact_keys(
        data,
        {
            "schema_version",
            "config_status",
            "starting_state",
            "food",
            "furnace_levels",
            "weather_temperatures",
            "zone_modifiers",
        },
        "$",
    )
    if _integer(data["schema_version"], "$.schema_version", minimum=1) != 1:
        raise SurvivalConfigError("unsupported survival schema_version")

    starting = _object(data["starting_state"], "$.starting_state")
    _exact_keys(
        starting,
        {
            "population",
            "resources",
            "basic_residences",
            "basic_residence_capacity",
            "furnace_level",
            "trust",
            "panic",
        },
        "$.starting_state",
    )
    population = _object(starting["population"], "$.starting_state.population")
    _exact_keys(population, {"workers", "engineers", "children"}, "$.starting_state.population")
    resources = _object(starting["resources"], "$.starting_state.resources")
    _exact_keys(
        resources,
        {"coal", "wood", "steel", "raw_food", "cooked_food", "storage_capacity"},
        "$.starting_state.resources",
    )
    food = _object(data["food"], "$.food")
    _exact_keys(food, {"per_person", "raw_to_cooked_ratio"}, "$.food")

    raw_levels = _object(data["furnace_levels"], "$.furnace_levels")
    if set(raw_levels) != {"0", "1", "2", "3"}:
        raise SurvivalConfigError("$.furnace_levels must contain 0, 1, 2, and 3")
    levels: dict[int, FurnaceLevelRule] = {}
    for raw_level, raw_rule in raw_levels.items():
        rule = _object(raw_rule, f"$.furnace_levels.{raw_level}")
        _exact_keys(rule, {"coal_cost", "heating"}, f"$.furnace_levels.{raw_level}")
        levels[int(raw_level)] = FurnaceLevelRule(
            coal_cost=_integer(rule["coal_cost"], f"$.furnace_levels.{raw_level}.coal_cost", minimum=0),
            heating=_integer(rule["heating"], f"$.furnace_levels.{raw_level}.heating", minimum=0),
        )

    raw_weather = data["weather_temperatures"]
    if not isinstance(raw_weather, list):
        raise SurvivalConfigError("$.weather_temperatures must be an array")
    weather = tuple(
        _integer(value, f"$.weather_temperatures[{index}]")
        for index, value in enumerate(raw_weather)
    )
    raw_zones = _object(data["zone_modifiers"], "$.zone_modifiers")
    zones = {name: _integer(value, f"$.zone_modifiers.{name}") for name, value in raw_zones.items()}

    return SurvivalRules(
        population=StartingPopulationRules(
            workers=_integer(population["workers"], "$.starting_state.population.workers", minimum=0),
            engineers=_integer(population["engineers"], "$.starting_state.population.engineers", minimum=0),
            children=_integer(population["children"], "$.starting_state.population.children", minimum=0),
        ),
        resources=StartingResourceRules(
            coal=_integer(resources["coal"], "$.starting_state.resources.coal", minimum=0),
            wood=_integer(resources["wood"], "$.starting_state.resources.wood", minimum=0),
            steel=_integer(resources["steel"], "$.starting_state.resources.steel", minimum=0),
            raw_food=_integer(resources["raw_food"], "$.starting_state.resources.raw_food", minimum=0),
            cooked_food=_integer(resources["cooked_food"], "$.starting_state.resources.cooked_food", minimum=0),
            storage_capacity=_integer(resources["storage_capacity"], "$.starting_state.resources.storage_capacity", minimum=0),
        ),
        basic_residences=_integer(starting["basic_residences"], "$.starting_state.basic_residences", minimum=1),
        basic_residence_capacity=_integer(starting["basic_residence_capacity"], "$.starting_state.basic_residence_capacity", minimum=1),
        starting_furnace_level=_integer(starting["furnace_level"], "$.starting_state.furnace_level", minimum=0),
        starting_trust=_integer(starting["trust"], "$.starting_state.trust", minimum=0),
        starting_panic=_integer(starting["panic"], "$.starting_state.panic", minimum=0),
        food_per_person=_integer(food["per_person"], "$.food.per_person", minimum=1),
        raw_to_cooked_ratio=_integer(food["raw_to_cooked_ratio"], "$.food.raw_to_cooked_ratio", minimum=1),
        furnace_levels=levels,
        weather_temperatures=weather,
        zone_modifiers=zones,
    )
