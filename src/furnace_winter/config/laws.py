from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from furnace_winter.config.status import ConfigStatus


class LawConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LawRule:
    law_id: str
    required_all: tuple[str, ...]
    required_any: tuple[str, ...]
    mutually_exclusive: tuple[str, ...]
    unlock_buildings: tuple[str, ...]
    unlock_actions: tuple[str, ...]
    unlock_modes: tuple[str, ...]
    auto_enable: tuple[str, ...]
    trust_change: int | None
    panic_change: int | None
    confirmation_required: bool


@dataclass(frozen=True, slots=True)
class RationRule:
    mode_id: str
    food_numerator: int
    food_denominator: int
    required_law_id: str | None
    daily_trust_change: int
    daily_panic_change: int
    sick_after_days: int | None
    sick_population_divisor: int | None


@dataclass(frozen=True, slots=True)
class WorktimeRules:
    long_shift_output_numerator: int
    long_shift_output_denominator: int
    long_shift_daily_trust_change: int
    long_shift_daily_panic_change: int
    long_shift_day_3_extra_panic: int
    long_shift_day_5_extra_trust: int
    overtime_output_numerator: int
    overtime_output_denominator: int
    overtime_medical_research_numerator: int
    overtime_medical_research_denominator: int
    overtime_sick_divisor: int
    overtime_sick_minimum_if_staffed: int
    overtime_accident_risk_divisor: int
    overtime_cold_extra_sick_divisor: int
    long_shift_first_day_sick_divisor: int
    long_shift_consecutive_sick_divisor: int
    long_shift_cold_extra_sick_divisor: int
    overtime_trust_change: int
    overtime_panic_change: int


@dataclass(frozen=True, slots=True)
class MedicalActionRules:
    temporary_capacity_through_day: int
    temporary_capacity: int
    medical_ration_food_per_patient: int
    medical_ration_max_patients: int
    medical_ration_cooldown_days: int
    triage_cooldown_days: int | None


@dataclass(frozen=True, slots=True)
class SocialActionRules:
    emergency_ration_cooldown_days: int
    emergency_ration_trust_change: int
    emergency_ration_panic_change: int
    memorial_cooldown_days: int
    memorial_trust_change: int
    memorial_panic_change: int
    firepit_daily_panic_change: int
    unhandled_body_unit: int
    unhandled_body_trust_change: int
    unhandled_body_panic_change: int
    unhandled_body_crisis_threshold: int
    unhandled_body_crisis_extra_panic: int


@dataclass(frozen=True, slots=True)
class LawRules:
    status: ConfigStatus
    ordinary_cooldown_days: int
    laws: Mapping[str, LawRule]
    rations: Mapping[str, RationRule]
    worktime: WorktimeRules
    medical: MedicalActionRules
    actions: SocialActionRules

    def __post_init__(self) -> None:
        object.__setattr__(self, "laws", MappingProxyType(dict(self.laws)))
        object.__setattr__(self, "rations", MappingProxyType(dict(self.rations)))

    def validate(self) -> None:
        if not self.status.is_runtime:
            raise LawConfigError("law config status must be runtime-loadable")
        if self.ordinary_cooldown_days < 1:
            raise LawConfigError("ordinary law cooldown must be positive")
        law_ids = set(self.laws)
        for law_id, rule in self.laws.items():
            if law_id != rule.law_id:
                raise LawConfigError("law id must match its map key")
            referenced = set(rule.required_all) | set(rule.required_any) | set(rule.mutually_exclusive)
            missing = referenced - law_ids
            if missing:
                raise LawConfigError(f"law {law_id!r} references unknown laws: {sorted(missing)}")
            if law_id in referenced:
                raise LawConfigError(f"law {law_id!r} cannot reference itself")
            for conflicting_id in rule.mutually_exclusive:
                if law_id not in self.laws[conflicting_id].mutually_exclusive:
                    raise LawConfigError(
                        "mutually exclusive law references must be symmetric"
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit_required_all(law_id: str) -> None:
            if law_id in visiting:
                raise LawConfigError("required_all law prerequisites must be acyclic")
            if law_id in visited:
                return
            visiting.add(law_id)
            for prerequisite_id in self.laws[law_id].required_all:
                visit_required_all(prerequisite_id)
            visiting.remove(law_id)
            visited.add(law_id)

        for law_id in self.laws:
            visit_required_all(law_id)
        if set(self.rations) != {"normal", "coarse_soup", "rice_porridge", "emergency"}:
            raise LawConfigError("ration catalog must contain the four V1 modes")
        for mode_id, ration in self.rations.items():
            if mode_id != ration.mode_id:
                raise LawConfigError("ration mode id must match its map key")
            if ration.food_numerator <= 0 or ration.food_denominator <= 0:
                raise LawConfigError("ration food ratio must be positive")
            if ration.required_law_id is not None and ration.required_law_id not in law_ids:
                raise LawConfigError("ration references an unknown law")
            if (ration.sick_after_days is None) != (ration.sick_population_divisor is None):
                raise LawConfigError("ration sickness threshold and divisor must be paired")
            if ration.sick_after_days is not None and ration.sick_after_days <= 0:
                raise LawConfigError("ration sickness threshold must be positive")
            if (
                ration.sick_population_divisor is not None
                and ration.sick_population_divisor <= 0
            ):
                raise LawConfigError("ration sickness divisor must be positive")
        positive_values = (
            self.worktime.long_shift_output_numerator,
            self.worktime.long_shift_output_denominator,
            self.worktime.overtime_output_numerator,
            self.worktime.overtime_output_denominator,
            self.worktime.overtime_medical_research_numerator,
            self.worktime.overtime_medical_research_denominator,
            self.worktime.overtime_sick_divisor,
            self.worktime.overtime_sick_minimum_if_staffed,
            self.worktime.overtime_accident_risk_divisor,
            self.worktime.overtime_cold_extra_sick_divisor,
            self.worktime.long_shift_first_day_sick_divisor,
            self.worktime.long_shift_consecutive_sick_divisor,
            self.worktime.long_shift_cold_extra_sick_divisor,
            self.medical.temporary_capacity,
            self.medical.medical_ration_food_per_patient,
            self.medical.medical_ration_max_patients,
            self.medical.medical_ration_cooldown_days,
            self.actions.emergency_ration_cooldown_days,
            self.actions.memorial_cooldown_days,
            self.actions.unhandled_body_unit,
            self.actions.unhandled_body_crisis_threshold,
        )
        if any(value <= 0 for value in positive_values):
            raise LawConfigError("positive law numeric values must be greater than zero")
        if self.medical.temporary_capacity_through_day < 0:
            raise LawConfigError("temporary medical capacity day must be nonnegative")
        if (
            self.medical.triage_cooldown_days is not None
            and self.medical.triage_cooldown_days <= 0
        ):
            raise LawConfigError("triage cooldown must be positive when configured")


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LawConfigError(f"{path} must be an object")
    return value


def _expect_keys(data: Mapping[str, Any], expected: set[str], path: str) -> None:
    missing = expected - set(data)
    unknown = set(data) - expected
    if missing or unknown:
        raise LawConfigError(
            f"{path} fields mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
        )


def _integer(value: Any, path: str, *, optional: bool = False) -> int | None:
    if value is None and optional:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise LawConfigError(f"{path} must be an integer")
    return value


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise LawConfigError(f"{path} must be an array of non-empty strings")
    if len(set(value)) != len(value):
        raise LawConfigError(f"{path} must not contain duplicates")
    return tuple(value)


def load_law_rules(path: Path) -> LawRules:
    data = _object(json.loads(Path(path).read_text(encoding="utf-8-sig")), "$")
    _expect_keys(
        data,
        {
            "schema_version",
            "config_status",
            "ordinary_cooldown_days",
            "laws",
            "rations",
            "worktime",
            "medical",
            "actions",
        },
        "$",
    )
    try:
        status = ConfigStatus(data["config_status"])
    except (KeyError, ValueError) as exc:
        raise LawConfigError("invalid law config status") from exc
    if data.get("schema_version") != 1:
        raise LawConfigError("unsupported law schema version")

    laws: dict[str, LawRule] = {}
    for law_id, raw in _object(data.get("laws"), "$.laws").items():
        if not isinstance(law_id, str) or not law_id:
            raise LawConfigError("law ids must be non-empty strings")
        item = _object(raw, f"$.laws.{law_id}")
        _expect_keys(
            item,
            {
                "required_all",
                "required_any",
                "mutually_exclusive",
                "unlock_buildings",
                "unlock_actions",
                "unlock_modes",
                "auto_enable",
                "trust_change",
                "panic_change",
                "confirmation_required",
            },
            f"$.laws.{law_id}",
        )
        laws[law_id] = LawRule(
            law_id=law_id,
            required_all=_strings(item.get("required_all"), f"$.laws.{law_id}.required_all"),
            required_any=_strings(item.get("required_any"), f"$.laws.{law_id}.required_any"),
            mutually_exclusive=_strings(item.get("mutually_exclusive"), f"$.laws.{law_id}.mutually_exclusive"),
            unlock_buildings=_strings(item.get("unlock_buildings"), f"$.laws.{law_id}.unlock_buildings"),
            unlock_actions=_strings(item.get("unlock_actions"), f"$.laws.{law_id}.unlock_actions"),
            unlock_modes=_strings(item.get("unlock_modes"), f"$.laws.{law_id}.unlock_modes"),
            auto_enable=_strings(item.get("auto_enable"), f"$.laws.{law_id}.auto_enable"),
            trust_change=_integer(item.get("trust_change"), f"$.laws.{law_id}.trust_change", optional=True),
            panic_change=_integer(item.get("panic_change"), f"$.laws.{law_id}.panic_change", optional=True),
            confirmation_required=item.get("confirmation_required", False),
        )
        if not isinstance(laws[law_id].confirmation_required, bool):
            raise LawConfigError("confirmation_required must be boolean")

    rations: dict[str, RationRule] = {}
    for mode_id, raw in _object(data.get("rations"), "$.rations").items():
        item = _object(raw, f"$.rations.{mode_id}")
        _expect_keys(
            item,
            {
                "food_numerator",
                "food_denominator",
                "required_law_id",
                "daily_trust_change",
                "daily_panic_change",
                "sick_after_days",
                "sick_population_divisor",
            },
            f"$.rations.{mode_id}",
        )
        required_law_id = item.get("required_law_id")
        if required_law_id is not None and not isinstance(required_law_id, str):
            raise LawConfigError("required_law_id must be a string or null")
        rations[str(mode_id)] = RationRule(
            mode_id=str(mode_id),
            food_numerator=int(_integer(item.get("food_numerator"), f"$.rations.{mode_id}.food_numerator")),
            food_denominator=int(_integer(item.get("food_denominator"), f"$.rations.{mode_id}.food_denominator")),
            required_law_id=required_law_id,
            daily_trust_change=int(_integer(item.get("daily_trust_change"), f"$.rations.{mode_id}.daily_trust_change")),
            daily_panic_change=int(_integer(item.get("daily_panic_change"), f"$.rations.{mode_id}.daily_panic_change")),
            sick_after_days=_integer(item.get("sick_after_days"), f"$.rations.{mode_id}.sick_after_days", optional=True),
            sick_population_divisor=_integer(item.get("sick_population_divisor"), f"$.rations.{mode_id}.sick_population_divisor", optional=True),
        )

    worktime = _object(data.get("worktime"), "$.worktime")
    medical = _object(data.get("medical"), "$.medical")
    actions = _object(data.get("actions"), "$.actions")
    _expect_keys(worktime, set(WorktimeRules.__dataclass_fields__), "$.worktime")
    _expect_keys(medical, set(MedicalActionRules.__dataclass_fields__), "$.medical")
    _expect_keys(actions, set(SocialActionRules.__dataclass_fields__), "$.actions")
    rules = LawRules(
        status=status,
        ordinary_cooldown_days=int(_integer(data.get("ordinary_cooldown_days"), "$.ordinary_cooldown_days")),
        laws=laws,
        rations=rations,
        worktime=WorktimeRules(**{key: int(_integer(worktime.get(key), f"$.worktime.{key}")) for key in WorktimeRules.__dataclass_fields__}),
        medical=MedicalActionRules(**{
            key: _integer(medical.get(key), f"$.medical.{key}", optional=key == "triage_cooldown_days")
            for key in MedicalActionRules.__dataclass_fields__
        }),
        actions=SocialActionRules(**{key: int(_integer(actions.get(key), f"$.actions.{key}")) for key in SocialActionRules.__dataclass_fields__}),
    )
    rules.validate()
    return rules
