from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file
from furnace_winter.config.status import ConfigStatus


class OathOrderConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OathOrderUnlockRules:
    ordinary_day: int
    ordinary_social_laws: int
    guaranteed_day: int
    law_cooldown_days: int


@dataclass(frozen=True, slots=True)
class OldCityRules:
    trigger_day: int
    daily_growth: int
    daily_growth_cap: int
    daily_decline_cap: int
    countdown_days: int
    countdown_cap_day: int
    initial_minimum: int
    initial_percent: int
    low_minimum: int
    low_percent: int
    middle_minimum: int
    middle_percent: int
    high_minimum: int
    high_percent: int


@dataclass(frozen=True, slots=True)
class RouteLawRule:
    law_id: str
    route: str
    requires: tuple[str, ...]
    trust: int
    panic: int


@dataclass(frozen=True, slots=True)
class RouteActionRule:
    action_id: str
    route: str
    required_law: str
    cooldown_days: int
    trust: int
    panic: int
    cooked_food: int
    old_city: int


@dataclass(frozen=True, slots=True)
class OathOrderRules:
    schema_version: int
    config_status: ConfigStatus
    unlock: OathOrderUnlockRules
    old_city: OldCityRules
    laws: Mapping[str, RouteLawRule]
    actions: Mapping[str, RouteActionRule]

    def __post_init__(self) -> None:
        object.__setattr__(self, "laws", MappingProxyType(dict(self.laws)))
        object.__setattr__(self, "actions", MappingProxyType(dict(self.actions)))


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OathOrderConfigError(f"{path} must be an object")
    return dict(value)


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise OathOrderConfigError(
            f"{path} fields mismatch: missing={sorted(expected - set(value))}, "
            f"unknown={sorted(set(value) - expected)}"
        )


def _integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise OathOrderConfigError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise OathOrderConfigError(f"{path} must be at least {minimum}")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise OathOrderConfigError(f"{path} must be a normalized string")
    return value


def _string_list(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise OathOrderConfigError(f"{path} must be an array")
    result = tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(value))
    if len(result) != len(set(result)):
        raise OathOrderConfigError(f"{path} must not contain duplicates")
    return result


def load_oath_order_rules(path: Path) -> OathOrderRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact(
        data,
        {"schema_version", "config_status", "unlock", "old_city", "laws", "actions"},
        "$",
    )
    schema_version = _integer(data["schema_version"], "$.schema_version", minimum=1)
    if schema_version != 1:
        raise OathOrderConfigError("unsupported oath/order schema_version")

    raw_unlock = _object(data["unlock"], "$.unlock")
    unlock_fields = {
        "ordinary_day", "ordinary_social_laws", "guaranteed_day", "law_cooldown_days"
    }
    _exact(raw_unlock, unlock_fields, "$.unlock")
    unlock = OathOrderUnlockRules(
        **{key: _integer(raw_unlock[key], f"$.unlock.{key}", minimum=1) for key in unlock_fields}
    )
    if unlock != OathOrderUnlockRules(30, 8, 35, 2):
        raise OathOrderConfigError("Patch 008 unlock boundaries must remain 30/8/35/2")

    raw_old_city = _object(data["old_city"], "$.old_city")
    old_city_fields = {
        "trigger_day", "daily_growth", "daily_growth_cap", "daily_decline_cap",
        "countdown_days", "countdown_cap_day", "initial_minimum", "initial_percent",
        "low_minimum", "low_percent", "middle_minimum", "middle_percent",
        "high_minimum", "high_percent",
    }
    _exact(raw_old_city, old_city_fields, "$.old_city")
    old_city = OldCityRules(
        **{
            key: _integer(
                raw_old_city[key],
                f"$.old_city.{key}",
                minimum=None if key == "daily_decline_cap" else 0,
            )
            for key in old_city_fields
        }
    )
    if (
        old_city.trigger_day != 24
        or old_city.countdown_cap_day != 48
        or old_city.daily_growth_cap != 6
        or old_city.daily_decline_cap != -3
    ):
        raise OathOrderConfigError("Patch 008 old-city fixed boundaries changed")

    law_ids = {
        "guard_oath", "mourning_bell", "shared_meal", "ember_roster", "stay_oath",
        "final_oath", "city_patrol_order", "morning_roll_call",
        "unified_announcement", "temporary_detain", "household_registry_check",
        "highest_order",
    }
    raw_laws = _object(data["laws"], "$.laws")
    if set(raw_laws) != law_ids:
        raise OathOrderConfigError("law catalog must match the sealed Patch 008 ids")
    laws: dict[str, RouteLawRule] = {}
    for law_id, value in raw_laws.items():
        item = _object(value, f"$.laws.{law_id}")
        _exact(item, {"route", "requires", "trust", "panic"}, f"$.laws.{law_id}")
        route = _string(item["route"], f"$.laws.{law_id}.route")
        if route not in {"oath", "iron"}:
            raise OathOrderConfigError("law route must be oath or iron")
        requires = _string_list(item["requires"], f"$.laws.{law_id}.requires")
        if set(requires) - law_ids:
            raise OathOrderConfigError("law prerequisite is unknown")
        laws[law_id] = RouteLawRule(
            law_id, route, requires,
            _integer(item["trust"], f"$.laws.{law_id}.trust"),
            _integer(item["panic"], f"$.laws.{law_id}.panic"),
        )

    action_ids = {
        "guard_oath", "mourning_bell", "shared_meal", "stay_persuasion",
        "patrol", "announcement", "detain", "registry_check",
    }
    raw_actions = _object(data["actions"], "$.actions")
    if set(raw_actions) != action_ids:
        raise OathOrderConfigError("action catalog must match the sealed Patch 008 ids")
    actions: dict[str, RouteActionRule] = {}
    for action_id, value in raw_actions.items():
        item = _object(value, f"$.actions.{action_id}")
        fields = {
            "route", "required_law", "cooldown_days", "trust", "panic",
            "cooked_food", "old_city",
        }
        _exact(item, fields, f"$.actions.{action_id}")
        route = _string(item["route"], f"$.actions.{action_id}.route")
        required_law = _string(item["required_law"], f"$.actions.{action_id}.required_law")
        if required_law not in laws or laws[required_law].route != route:
            raise OathOrderConfigError("action law and route must agree")
        actions[action_id] = RouteActionRule(
            action_id, route, required_law,
            _integer(item["cooldown_days"], f"$.actions.{action_id}.cooldown_days", minimum=1),
            _integer(item["trust"], f"$.actions.{action_id}.trust"),
            _integer(item["panic"], f"$.actions.{action_id}.panic"),
            _integer(item["cooked_food"], f"$.actions.{action_id}.cooked_food"),
            _integer(item["old_city"], f"$.actions.{action_id}.old_city"),
        )
    return OathOrderRules(
        schema_version, loaded.status, unlock, old_city, laws, actions
    )
