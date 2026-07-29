from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from furnace_winter.config.buildings import BuildingRules
from furnace_winter.config.maps import (
    SEALED_MAP_ORDER,
    MapRules,
    MapTemplateRule,
)
from furnace_winter.gameplay.end_day import EndDayEngine
from furnace_winter.models import DeterministicRandom, GameState, MapState


MAP_SELECTION_MODES = frozenset({"random", "manual"})
_PERSISTED_SELECTION_MODES = MAP_SELECTION_MODES | {"legacy_default"}


def _map_state(
    rules: MapRules,
    template: MapTemplateRule,
    selection_mode: str,
) -> MapState:
    shared = rules.shared
    return MapState(
        map_key=template.map_key,
        selection_mode=selection_mode,
        display_name_zh=template.display_name_zh,
        difficulty_zh=template.difficulty_zh,
        small_coal_piles=shared.small_coal_piles,
        small_wood_piles=shared.small_wood_piles,
        small_steel_piles=shared.small_steel_piles,
        initial_hunting_grounds=shared.initial_hunting_grounds,
        total_hunting_grounds=shared.total_hunting_grounds,
        forest_zones=shared.forest_zones,
        large_coal_mine_points=template.large_coal_mine_points,
        large_steel_mine_points=template.large_steel_mine_points,
    )


def _weighted_map_key(
    rules: MapRules,
    random: DeterministicRandom,
) -> str:
    total = sum(rules.random_integer_weights.values())
    draw = random.randint(1, total)
    cumulative = 0
    for map_key in SEALED_MAP_ORDER:
        weight = rules.random_integer_weights[map_key]
        cumulative += weight
        if draw <= cumulative:
            return map_key
    raise RuntimeError("map weight selection did not resolve")


def select_initial_map(
    state: GameState,
    rules: MapRules,
    *,
    selection_mode: str = "random",
    map_key: str | None = None,
) -> None:
    if selection_mode not in MAP_SELECTION_MODES:
        raise ValueError(
            "map selection mode must be 'random' or 'manual'"
        )
    random = DeterministicRandom.from_state(state.random)
    if selection_mode == "random":
        if map_key is not None:
            raise ValueError("random map selection cannot specify map_key")
        selected_key = _weighted_map_key(rules, random)
        state.random = random.snapshot()
    else:
        if map_key is None:
            raise ValueError("manual map selection requires map_key")
        if map_key not in rules.templates:
            raise ValueError(
                f"unknown map_key {map_key!r}; "
                f"expected one of {sorted(rules.templates)}"
            )
        selected_key = map_key
    state.map = _map_state(
        rules,
        rules.templates[selected_key],
        selection_mode,
    )


def _expected_random_map_key(state: GameState, rules: MapRules) -> str:
    random = DeterministicRandom(state.random.seed)
    return _weighted_map_key(rules, random)


class MapSystem:
    """Validate the sealed V1 map identity and resource capacities."""

    def __init__(
        self,
        rules: MapRules,
        building_rules: BuildingRules,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules

    def install(self, engine: EndDayEngine) -> None:
        engine.register_state_validator(self.validate_state)

    def validate_state(self, state: GameState) -> None:
        map_state = state.map
        if map_state.selection_mode not in _PERSISTED_SELECTION_MODES:
            raise ValueError("state contains an unsupported map selection mode")
        template = self.rules.templates.get(map_state.map_key)
        if template is None:
            raise ValueError("state contains an unknown map key")
        expected = _map_state(
            self.rules,
            template,
            map_state.selection_mode,
        )
        if map_state != expected:
            raise ValueError(
                "map state does not match the selected map template"
            )
        if (
            map_state.selection_mode == "legacy_default"
            and map_state.map_key != self.rules.legacy_default_map_key
        ):
            raise ValueError(
                "legacy map state must use the configured migration default"
            )
        if map_state.selection_mode == "random":
            if state.random.draws < 1:
                raise ValueError(
                    "random map selection must consume the unified random stream"
                )
            if map_state.map_key != _expected_random_map_key(
                state, self.rules
            ):
                raise ValueError(
                    "random map does not match the initial seed draw"
                )

        point_counts = {"coal": 0, "wood": 0, "steel": 0}
        for point in state.surface_resource_points.values():
            if point.resource_type in point_counts:
                point_counts[point.resource_type] += 1
        expected_point_counts = {
            "coal": map_state.small_coal_piles,
            "wood": map_state.small_wood_piles,
            "steel": map_state.small_steel_piles,
        }
        if point_counts != expected_point_counts:
            raise ValueError(
                "surface resource points do not match the selected map"
            )
        management = state.building_management
        if management.total_hunting_areas != map_state.total_hunting_grounds:
            raise ValueError("hunting area count does not match the map")
        if management.forest_zones != map_state.forest_zones:
            raise ValueError("forest zone count does not match the map")
        if len(self.building_rules.resource_anchors["hunting_area"]) != (
            map_state.total_hunting_grounds
        ):
            raise ValueError(
                "building hunting anchors do not match the map"
            )
        if len(self.building_rules.resource_anchors["forest_zone"]) != (
            map_state.forest_zones
        ):
            raise ValueError("building forest anchors do not match the map")

    def view(self, state: GameState) -> Mapping[str, Any]:
        return deepcopy(
            {
                "map_key": state.map.map_key,
                "display_name_zh": state.map.display_name_zh,
                "difficulty_zh": state.map.difficulty_zh,
                "selection_mode": state.map.selection_mode,
                "small_resource_points": {
                    "coal": state.map.small_coal_piles,
                    "wood": state.map.small_wood_piles,
                    "steel": state.map.small_steel_piles,
                },
                "hunting_grounds": {
                    "available": state.building_management.available_hunting_areas,
                    "total": state.map.total_hunting_grounds,
                },
                "forest_zones": state.map.forest_zones,
                "large_mine_points": {
                    "coal": state.map.large_coal_mine_points,
                    "steel": state.map.large_steel_mine_points,
                },
            }
        )
