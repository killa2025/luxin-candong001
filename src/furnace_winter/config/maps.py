from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file


class MapConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MapTemplateRule:
    map_key: str
    display_name_zh: str
    difficulty_zh: str
    large_coal_mine_points: int
    large_steel_mine_points: int


@dataclass(frozen=True, slots=True)
class SharedMapRules:
    small_coal_piles: int
    small_wood_piles: int
    small_steel_piles: int
    initial_hunting_grounds: int
    total_hunting_grounds: int
    forest_zones: int


@dataclass(frozen=True, slots=True)
class MapRules:
    default_selection_mode: str
    legacy_default_map_key: str
    random_integer_weights: Mapping[str, int]
    shared: SharedMapRules
    templates: Mapping[str, MapTemplateRule]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "random_integer_weights",
            MappingProxyType(dict(self.random_integer_weights)),
        )
        object.__setattr__(
            self,
            "templates",
            MappingProxyType(dict(self.templates)),
        )


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MapConfigError(f"{path} must be an object")
    return dict(value)


def _exact(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing or unknown:
        raise MapConfigError(
            f"{path} keys do not match schema; "
            f"missing={missing}, unknown={unknown}"
        )


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MapConfigError(
            f"{path} must be an integer of at least {minimum}"
        )
    return value


def _string(value: Any, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise MapConfigError(
            f"{path} must be a normalized non-empty string"
        )
    return value


def load_map_rules(path: Path) -> MapRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact(
        data,
        {
            "schema_version",
            "config_status",
            "selection",
            "shared",
            "templates",
        },
        "$",
    )
    if _integer(data["schema_version"], "$.schema_version", minimum=1) != 1:
        raise MapConfigError("unsupported map schema_version")

    selection = _object(data["selection"], "$.selection")
    _exact(
        selection,
        {
            "default_mode",
            "legacy_default_map_key",
            "random_integer_weights",
        },
        "$.selection",
    )
    default_mode = _string(
        selection["default_mode"], "$.selection.default_mode"
    )
    if default_mode != "random":
        raise MapConfigError("the sealed default map mode must be random")

    shared_data = _object(data["shared"], "$.shared")
    _exact(
        shared_data,
        {
            "small_coal_piles",
            "small_wood_piles",
            "small_steel_piles",
            "initial_hunting_grounds",
            "total_hunting_grounds",
            "forest_zones",
        },
        "$.shared",
    )
    shared = SharedMapRules(
        small_coal_piles=_integer(
            shared_data["small_coal_piles"],
            "$.shared.small_coal_piles",
            minimum=1,
        ),
        small_wood_piles=_integer(
            shared_data["small_wood_piles"],
            "$.shared.small_wood_piles",
            minimum=1,
        ),
        small_steel_piles=_integer(
            shared_data["small_steel_piles"],
            "$.shared.small_steel_piles",
            minimum=1,
        ),
        initial_hunting_grounds=_integer(
            shared_data["initial_hunting_grounds"],
            "$.shared.initial_hunting_grounds",
            minimum=1,
        ),
        total_hunting_grounds=_integer(
            shared_data["total_hunting_grounds"],
            "$.shared.total_hunting_grounds",
            minimum=1,
        ),
        forest_zones=_integer(
            shared_data["forest_zones"],
            "$.shared.forest_zones",
            minimum=1,
        ),
    )
    if shared.initial_hunting_grounds > shared.total_hunting_grounds:
        raise MapConfigError(
            "initial hunting grounds cannot exceed total hunting grounds"
        )

    raw_templates = _object(data["templates"], "$.templates")
    expected_map_keys = {
        "rustbone_tundra",
        "black_ash_lowland",
        "twin_source_rift",
    }
    if set(raw_templates) != expected_map_keys:
        raise MapConfigError(
            "templates must define the three sealed V1 map keys"
        )
    templates: dict[str, MapTemplateRule] = {}
    template_keys = {
        "display_name_zh",
        "difficulty_zh",
        "large_coal_mine_points",
        "large_steel_mine_points",
    }
    for map_key, raw_value in raw_templates.items():
        checked_key = _string(map_key, "$.templates key")
        item = _object(raw_value, f"$.templates.{checked_key}")
        _exact(item, template_keys, f"$.templates.{checked_key}")
        templates[checked_key] = MapTemplateRule(
            map_key=checked_key,
            display_name_zh=_string(
                item["display_name_zh"],
                f"$.templates.{checked_key}.display_name_zh",
            ),
            difficulty_zh=_string(
                item["difficulty_zh"],
                f"$.templates.{checked_key}.difficulty_zh",
            ),
            large_coal_mine_points=_integer(
                item["large_coal_mine_points"],
                f"$.templates.{checked_key}.large_coal_mine_points",
                minimum=1,
            ),
            large_steel_mine_points=_integer(
                item["large_steel_mine_points"],
                f"$.templates.{checked_key}.large_steel_mine_points",
                minimum=1,
            ),
        )
    if len({item.display_name_zh for item in templates.values()}) != 3:
        raise MapConfigError("map display names must be unique")

    raw_weights = _object(
        selection["random_integer_weights"],
        "$.selection.random_integer_weights",
    )
    if set(raw_weights) != expected_map_keys:
        raise MapConfigError(
            "random weights must exactly match the map templates"
        )
    weights = {
        map_key: _integer(
            value,
            f"$.selection.random_integer_weights.{map_key}",
            minimum=1,
        )
        for map_key, value in raw_weights.items()
    }
    if sum(weights.values()) != 100:
        raise MapConfigError("sealed integer map weights must total 100")

    legacy_default = _string(
        selection["legacy_default_map_key"],
        "$.selection.legacy_default_map_key",
    )
    if legacy_default not in templates:
        raise MapConfigError("legacy default map must reference a template")

    return MapRules(
        default_selection_mode=default_mode,
        legacy_default_map_key=legacy_default,
        random_integer_weights=weights,
        shared=shared,
        templates=templates,
    )
