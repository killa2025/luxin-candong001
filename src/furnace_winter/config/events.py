from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.loader import load_config_file
from furnace_winter.config.status import ConfigStatus


class EventConfigError(ValueError):
    pass


_EVENT_IDS = {
    "empty_pot",
    "raw_food_dispute",
    "medical_beds_emergency",
    "severe_case_backlog",
    "first_body",
    "bodies_under_snow",
    "children_request",
    "red_frozen_hands",
    "long_shift_collapse",
    "overtime_empty_post",
    "coal_bottom",
    "furnace_redline",
    "cold_house_night",
    "trust_crack",
    "city_unrest",
    "black_frost_echo",
    "final_preparation_window",
    "city_night_terror",
    "seventh_frost_start",
}
_ARRIVAL_IDS = {"arrival_day6", "arrival_day19", "arrival_day37"}
_ARRIVAL_DAYS = {"arrival_day6": 6, "arrival_day19": 19, "arrival_day37": 37}
_EVENT_PROMISES: dict[str, tuple[str, str]] = {
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
_THRESHOLD_IDS = {
    "food_warning_days_x10",
    "empty_pot_days_x10",
    "raw_food_days",
    "raw_food_window_days",
    "canteen_outage_days",
    "medical_gap_warning",
    "medical_gap_event",
    "medical_gap_major",
    "severe_patients",
    "persistent_severe_patients",
    "persistent_severe_days",
    "unhandled_body_event",
    "unhandled_body_major",
    "children_request_day_min",
    "unprotected_children",
    "child_labor_risk_points",
    "child_harm_from_work",
    "long_shift_days",
    "long_shift_risk_points",
    "overtime_window_days",
    "overtime_uses",
    "coal_warning_days_x10",
    "coal_event_days_x10",
    "coal_major_days_x10_after_black_frost",
    "furnace_pressure_warning",
    "furnace_pressure_event",
    "furnace_pressure_forced",
    "homeless_warning",
    "homeless_event",
    "homeless_major",
    "cold_exposure_event_level",
    "cold_exposure_major_level",
    "cold_exposure_status_delay_days",
    "cold_house_day_min",
    "trust_warning",
    "trust_event",
    "trust_major",
    "panic_warning",
    "panic_event",
    "panic_major",
}


@dataclass(frozen=True, slots=True)
class QueueRules:
    max_major_per_day: int
    max_normal_with_major: int
    max_normal_without_major: int


@dataclass(frozen=True, slots=True)
class PromiseEffectRule:
    success_trust: int
    success_panic: int
    failure_trust: int
    failure_panic: int


@dataclass(frozen=True, slots=True)
class PromiseRules:
    max_active: int
    deadline_cap_start_day: int
    deadline_cap_day: int
    disabled_from_day: int
    deadlines: Mapping[str, int]
    effects: Mapping[str, PromiseEffectRule]

    def __post_init__(self) -> None:
        object.__setattr__(self, "deadlines", MappingProxyType(dict(self.deadlines)))
        object.__setattr__(self, "effects", MappingProxyType(dict(self.effects)))


@dataclass(frozen=True, slots=True)
class EventRule:
    event_id: str
    priority: int
    cooldown_days: int
    max_per_game: int
    promise_type: str | None
    promise_severity: str | None


@dataclass(frozen=True, slots=True)
class ArrivalEffectRule:
    total: int
    workers: int
    engineers: int
    children: int
    sick: int
    critical: int
    disabled: int
    trust: int
    panic: int
    old_city: int


@dataclass(frozen=True, slots=True)
class FixedArrivalRule:
    event_id: str
    day: int
    options: Mapping[str, ArrivalEffectRule]

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", MappingProxyType(dict(self.options)))


@dataclass(frozen=True, slots=True)
class EventRules:
    schema_version: int
    config_status: ConfigStatus
    queue: QueueRules
    thresholds: Mapping[str, int]
    promise: PromiseRules
    events: Mapping[str, EventRule]
    fixed_arrivals: Mapping[str, FixedArrivalRule]
    frostfall_warning_days: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "thresholds", MappingProxyType(dict(self.thresholds)))
        object.__setattr__(self, "events", MappingProxyType(dict(self.events)))
        object.__setattr__(
            self, "fixed_arrivals", MappingProxyType(dict(self.fixed_arrivals))
        )


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EventConfigError(f"{path} must be an object")
    return dict(value)


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing or unknown:
        raise EventConfigError(
            f"{path} fields mismatch: missing={missing}, unknown={unknown}"
        )


def _integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise EventConfigError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise EventConfigError(f"{path} must be at least {minimum}")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise EventConfigError(f"{path} must be a normalized string or null")
    return value


def _int_map(value: Any, path: str, *, minimum: int | None = None) -> dict[str, int]:
    data = _object(value, path)
    return {
        key: _integer(item, f"{path}.{key}", minimum=minimum)
        for key, item in data.items()
    }


def load_event_rules(path: Path) -> EventRules:
    loaded = load_config_file(path)
    data = dict(loaded.data)
    _exact(
        data,
        {
            "schema_version",
            "config_status",
            "queue",
            "thresholds",
            "promise",
            "events",
            "fixed_arrivals",
            "frostfall_warning_days",
        },
        "$",
    )
    schema_version = _integer(data["schema_version"], "$.schema_version", minimum=1)
    if schema_version != 1:
        raise EventConfigError("unsupported event schema_version")

    raw_queue = _object(data["queue"], "$.queue")
    _exact(
        raw_queue,
        {"max_major_per_day", "max_normal_with_major", "max_normal_without_major"},
        "$.queue",
    )
    queue = QueueRules(
        **{
            key: _integer(value, f"$.queue.{key}", minimum=0)
            for key, value in raw_queue.items()
        }
    )
    if queue != QueueRules(1, 1, 2):
        raise EventConfigError("Patch 007 queue limits must remain 1/1/2")

    raw_promise = _object(data["promise"], "$.promise")
    _exact(
        raw_promise,
        {
            "max_active",
            "deadline_cap_start_day",
            "deadline_cap_day",
            "disabled_from_day",
            "deadlines",
            "effects",
        },
        "$.promise",
    )
    deadlines = _int_map(raw_promise["deadlines"], "$.promise.deadlines", minimum=1)
    expected_promise_types = {
        "food", "medical", "housing", "body", "children",
        "labor", "coal", "furnace", "trust", "panic",
    }
    if set(deadlines) != expected_promise_types:
        raise EventConfigError("promise deadlines must define the ten Patch 007 types")
    raw_effects = _object(raw_promise["effects"], "$.promise.effects")
    if set(raw_effects) != {"ordinary", "serious", "critical"}:
        raise EventConfigError("promise effects must define three severity tiers")
    effects: dict[str, PromiseEffectRule] = {}
    for severity, raw_effect in raw_effects.items():
        effect = _object(raw_effect, f"$.promise.effects.{severity}")
        _exact(
            effect,
            {"success_trust", "success_panic", "failure_trust", "failure_panic"},
            f"$.promise.effects.{severity}",
        )
        effects[severity] = PromiseEffectRule(
            **{
                key: _integer(value, f"$.promise.effects.{severity}.{key}")
                for key, value in effect.items()
            }
        )
    promise = PromiseRules(
        max_active=_integer(raw_promise["max_active"], "$.promise.max_active", minimum=1),
        deadline_cap_start_day=_integer(raw_promise["deadline_cap_start_day"], "$.promise.deadline_cap_start_day", minimum=1),
        deadline_cap_day=_integer(raw_promise["deadline_cap_day"], "$.promise.deadline_cap_day", minimum=1),
        disabled_from_day=_integer(raw_promise["disabled_from_day"], "$.promise.disabled_from_day", minimum=1),
        deadlines=deadlines,
        effects=effects,
    )
    if (promise.max_active, promise.deadline_cap_start_day, promise.deadline_cap_day, promise.disabled_from_day) != (2, 42, 48, 49):
        raise EventConfigError("Patch 007 promise boundary values changed")

    raw_events = _object(data["events"], "$.events")
    if set(raw_events) != _EVENT_IDS:
        raise EventConfigError("event catalog must match the Patch 007 sealed ids")
    events: dict[str, EventRule] = {}
    for event_id, raw_event in raw_events.items():
        item = _object(raw_event, f"$.events.{event_id}")
        _exact(
            item,
            {"priority", "cooldown_days", "max_per_game", "promise_type", "promise_severity"},
            f"$.events.{event_id}",
        )
        promise_type = _optional_string(item["promise_type"], f"$.events.{event_id}.promise_type")
        severity = _optional_string(item["promise_severity"], f"$.events.{event_id}.promise_severity")
        if (promise_type is None) != (severity is None):
            raise EventConfigError("event promise type and severity must both be present or absent")
        if promise_type is not None and promise_type not in deadlines:
            raise EventConfigError(f"event {event_id} uses an unknown promise type")
        if severity is not None and severity not in effects:
            raise EventConfigError(f"event {event_id} uses an unknown promise severity")
        expected_promise = _EVENT_PROMISES.get(event_id)
        if (promise_type, severity) != (
            expected_promise if expected_promise is not None else (None, None)
        ):
            raise EventConfigError(
                f"event {event_id} promise type or severity disagrees with Patch 007"
            )
        events[event_id] = EventRule(
            event_id=event_id,
            priority=_integer(item["priority"], f"$.events.{event_id}.priority", minimum=1),
            cooldown_days=_integer(item["cooldown_days"], f"$.events.{event_id}.cooldown_days", minimum=0),
            max_per_game=_integer(item["max_per_game"], f"$.events.{event_id}.max_per_game", minimum=0),
            promise_type=promise_type,
            promise_severity=severity,
        )

    arrivals: dict[str, FixedArrivalRule] = {}
    arrival_fields = {"total", "workers", "engineers", "children", "sick", "critical", "disabled", "trust", "panic", "old_city"}
    seen_days: set[int] = set()
    raw_arrivals = _object(data["fixed_arrivals"], "$.fixed_arrivals")
    if set(raw_arrivals) != _ARRIVAL_IDS:
        raise EventConfigError("fixed arrival catalog must match Patch 007")
    for event_id, raw_arrival in raw_arrivals.items():
        item = _object(raw_arrival, f"$.fixed_arrivals.{event_id}")
        _exact(item, {"day", "options"}, f"$.fixed_arrivals.{event_id}")
        day = _integer(item["day"], f"$.fixed_arrivals.{event_id}.day", minimum=1)
        if day != _ARRIVAL_DAYS[event_id]:
            raise EventConfigError(
                f"fixed arrival {event_id} must occur on day {_ARRIVAL_DAYS[event_id]}"
            )
        if day in seen_days:
            raise EventConfigError("fixed arrival days must be unique")
        seen_days.add(day)
        options: dict[str, ArrivalEffectRule] = {}
        raw_options = _object(item["options"], f"$.fixed_arrivals.{event_id}.options")
        if set(raw_options) != {"accept_all", "accept_partial", "reject"}:
            raise EventConfigError("fixed arrivals require the three sealed options")
        for option_id, raw_option in raw_options.items():
            effect = _object(raw_option, f"$.fixed_arrivals.{event_id}.options.{option_id}")
            _exact(effect, arrival_fields, f"$.fixed_arrivals.{event_id}.options.{option_id}")
            checked = {
                key: _integer(
                    value,
                    f"$.fixed_arrivals.{event_id}.options.{option_id}.{key}",
                    minimum=None if key in {"trust", "panic", "old_city"} else 0,
                )
                for key, value in effect.items()
            }
            if checked["total"] != sum(checked[key] for key in ("workers", "engineers", "children", "sick", "critical", "disabled")):
                raise EventConfigError("arrival total must match all population components")
            options[option_id] = ArrivalEffectRule(**checked)
        arrivals[event_id] = FixedArrivalRule(event_id, day, options)
    if seen_days != {6, 19, 37}:
        raise EventConfigError("fixed arrivals must occur on days 6, 19, and 37")

    warning_days_raw = data["frostfall_warning_days"]
    if not isinstance(warning_days_raw, list):
        raise EventConfigError("$.frostfall_warning_days must be an array")
    warning_days = tuple(
        _integer(value, f"$.frostfall_warning_days[{index}]", minimum=1)
        for index, value in enumerate(warning_days_raw)
    )
    if warning_days != (34, 42, 46, 48, 49):
        raise EventConfigError("frostfall warning nodes must remain 34/42/46/48/49")
    thresholds = _int_map(data["thresholds"], "$.thresholds", minimum=0)
    if set(thresholds) != _THRESHOLD_IDS:
        raise EventConfigError("threshold catalog must match Patch 007")
    if thresholds["raw_food_window_days"] != 3:
        raise EventConfigError("raw food event window must remain three days")
    ordered_thresholds = (
        ("food_warning_days_x10", "empty_pot_days_x10", ">="),
        ("medical_gap_warning", "medical_gap_event", "<="),
        ("medical_gap_event", "medical_gap_major", "<="),
        ("unhandled_body_event", "unhandled_body_major", "<="),
        ("coal_warning_days_x10", "coal_event_days_x10", ">="),
        (
            "coal_event_days_x10",
            "coal_major_days_x10_after_black_frost",
            ">=",
        ),
        ("furnace_pressure_warning", "furnace_pressure_event", "<="),
        ("furnace_pressure_event", "furnace_pressure_forced", "<="),
        ("homeless_warning", "homeless_event", "<="),
        ("homeless_event", "homeless_major", "<="),
        ("cold_exposure_event_level", "cold_exposure_major_level", "<="),
        ("trust_warning", "trust_event", ">="),
        ("trust_event", "trust_major", ">="),
        ("panic_warning", "panic_event", "<="),
        ("panic_event", "panic_major", "<="),
    )
    for left, right, relation in ordered_thresholds:
        valid = (
            thresholds[left] <= thresholds[right]
            if relation == "<="
            else thresholds[left] >= thresholds[right]
        )
        if not valid:
            raise EventConfigError(
                f"event thresholds must preserve {left} {relation} {right}"
            )
    return EventRules(
        schema_version=schema_version,
        config_status=loaded.status,
        queue=queue,
        thresholds=thresholds,
        promise=promise,
        events=events,
        fixed_arrivals=arrivals,
        frostfall_warning_days=warning_days,
    )
