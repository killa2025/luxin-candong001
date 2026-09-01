from __future__ import annotations

from hashlib import blake2b
from typing import TYPE_CHECKING

from furnace_winter.models.randomness import DeterministicRandom
from furnace_winter.models.state import (
    ENDING_ADDITIONAL_POOL_TAGS,
    ENDING_BODY_POOL_TEXT_IDS,
    ENDING_HARD_FAIL_BODY_POOL_TEXT_IDS,
    ENDING_INTERROGATION_POOL_BY_ENDING,
    ENDING_REPORT_DEATH_RECORD_TEXT_ID,
    ENDING_REPORT_NARRATIVE_POOL_TEXT_IDS,
    ENDING_REPORT_ZERO_FROST_DEATHS_TEXT_ID,
    ENDING_TITLE_TEXT_IDS,
    RunState,
)

if TYPE_CHECKING:
    from furnace_winter.models.state import GameState


SURVIVAL_BODY_CANDIDATES = {
    "high_victory": tuple(
        f"ending.high_victory.body.{index:02d}" for index in range(1, 4)
    ),
    "standard_victory": tuple(
        f"ending.standard_victory.body.{index:02d}" for index in range(1, 4)
    ),
    "bitter_victory": tuple(
        f"ending.bitter_victory.body.{index:02d}" for index in range(1, 5)
    ),
    "collapse_survival": tuple(
        f"ending.collapse_survival.body.{index:02d}" for index in range(1, 4)
    ),
    "ember_survival": tuple(
        f"ending.ember_survival.body.{index:02d}" for index in range(1, 4)
    ),
}
PLAYER_ENDED_BODY_CANDIDATES = tuple(
    f"ending.player_ended.body.{index:02d}" for index in range(1, 4)
)
HARD_FAIL_BODY_CANDIDATES = {
    "population_zero": tuple(
        f"ending.hard_fail.population_zero.body.{index:02d}"
        for index in range(1, 6)
    ),
    "core_collapse": tuple(
        f"ending.hard_fail.core_collapse.body.{index:02d}"
        for index in range(1, 6)
    ),
    "trust_exile": tuple(
        f"ending.hard_fail.trust_exile.body.{index:02d}"
        for index in range(1, 6)
    ),
    "panic_expelled": tuple(
        f"ending.hard_fail.panic_expelled.body.{index:02d}"
        for index in range(1, 6)
    ),
}
HARD_FAIL_CLOSING_CANDIDATES = tuple(
    f"ending.hard_fail.closing.{index:02d}" for index in range(1, 5)
)
REPORT_FUTURE_CANDIDATES = tuple(
    f"ending.report.future.{index:02d}" for index in range(1, 4)
)
ADDITIONAL_CANDIDATES = {
    topic: tuple(
        f"ending.additional.{topic}.{index:02d}" for index in range(1, 4)
    )
    for topic in ("death", "medical", "food", "core", "society", "housing")
}
INTERROGATION_CANDIDATES = {
    "high_victory": tuple(
        f"ending.interrogation.high_victory.{index:02d}"
        for index in range(1, 3)
    ),
    "standard_victory": tuple(
        f"ending.interrogation.general.{index:02d}"
        for index in range(1, 6)
    ),
    "bitter_victory": tuple(
        f"ending.interrogation.cost.{index:02d}" for index in range(1, 4)
    ),
    "collapse_survival": tuple(
        f"ending.interrogation.cost.{index:02d}" for index in range(1, 4)
    ),
    "ember_survival": tuple(
        f"ending.interrogation.ember.{index:02d}" for index in range(1, 3)
    ),
}

_ADDITIONAL_TOPICS = {
    "death": {"mass_death", "grave_city", "frost_survived_broken"},
    "medical": {
        "medical_strained",
        "medical_collapse",
        "silent_hospital",
        "survived_with_disabled",
    },
    "food": {"famine_survivor", "famine_city"},
    "core": {
        "coal_desperate",
        "cold_engine",
        "redline_survivor",
        "overload_burned_city",
        "heat_last_stand",
    },
    "society": {
        "broken_society",
        "oath_carried_zero_trust",
        "decree_carried_panic",
    },
    "housing": {
        "cold_houses",
        "frozen_homeless",
        "city_continuity_broken",
    },
}
_ADDITIONAL_LIMITS = {
    "high_victory": 1,
    "standard_victory": 2,
    "bitter_victory": 2,
    "collapse_survival": 3,
    "ember_survival": 3,
}
_PENDING_LONG_TEXT_IDS = {
    "children": "ending.children.full_text",
    "children_trace": "ending.trace.children_protected",
    "death": "ending.death_handling.full_text",
    "entertainment": "ending.entertainment.full_text",
    "final_decree": "ending.route.final_decree.full_text",
    "final_oath": "ending.route.final_oath.full_text",
    "iron": "ending.route.iron.full_text",
    "oath": "ending.route.oath.full_text",
    "old_city": "ending.old_city.full_text",
}
_PENDING_MEDICAL_TEXT_IDS = (
    "ending.additional.medical.01",
    "ending.additional.medical.02",
)
_PENDING_FOOD_TEXT_ID = "ending.additional.food.01"
_PENDING_REPORT_ILLNESS_TEXT_ID = (
    "ending.report.illness.no_operational_service"
)
_PENDING_REPORT_COAL_FOOD_TEXT_ID = "ending.report.coal_food.zero_stock"

_OLD_CITY_FULL_TEXT_IDS = {
    "scattered": "ending.old_city.scattered.full_text",
    "partial_exodus": "ending.old_city.partial_exodus.full_text",
    "large_exodus": "ending.old_city.large_exodus.full_text",
}
_OLD_CITY_PROMISE_TEXT_IDS = {
    "success": "ending.old_city.promise.success",
    "failure": "ending.old_city.promise.failure",
}
_PATCH_030_REPLACED_TRACE_TEXT_IDS = {
    "children": {"ending.trace.child_labor"},
    "route": {
        "ending.trace.oath_route",
        "ending.trace.iron_route",
        "ending.report.death_record.ember_roster",
    },
    "old_city": {"ending.trace.old_city"},
    "entertainment": {"ending.trace.entertainment"},
}


def _choose(state: GameState, key: str, candidates: tuple[str, ...]) -> str:
    if not candidates:
        raise ValueError("ending text selection requires at least one candidate")
    digest = blake2b(
        key.encode("utf-8"), digest_size=8, person=b"fw-ending-v1"
    ).digest()
    derived_seed = state.random.seed ^ int.from_bytes(digest, "big")
    random = DeterministicRandom(derived_seed)
    return candidates[random.randint(0, len(candidates) - 1)]


def _has_building(state: GameState, building_type: str) -> bool:
    return any(
        building.building_type == building_type and building.is_built
        for building in state.buildings.values()
    )


def _has_operational_building(state: GameState, building_type: str) -> bool:
    return any(
        building.building_type == building_type
        and building.is_built
        and building.is_operational
        for building in state.buildings.values()
    )


def _medical_history_proves_first_candidate(record: object) -> bool:
    return bool(
        getattr(record, "service_history_known", False)
        and getattr(record, "medical_operational_building_count", 0) > 0
        and getattr(record, "medical_building_capacity", 0) > 0
        and getattr(record, "actual_disease_deaths", 0) > 0
        and not getattr(record, "medical_collapse", False)
        and not getattr(record, "hospital_shutdown", False)
    )


def _medical_history_proves_second_candidate(record: object) -> bool:
    return bool(
        getattr(record, "service_history_known", False)
        and getattr(record, "medical_operational_building_count", 0) > 0
        and getattr(record, "medical_building_capacity", 0) > 0
        and getattr(record, "actual_disease_deaths", 0) > 0
        and getattr(record, "medical_overflow", False)
    )


def _canteen_history_is_proven(state: GameState) -> bool:
    return any(
        record.service_history_known and record.canteen_operational
        for record in state.final_frost.daily_records.values()
    )


def _survival_body_candidates(state: GameState) -> tuple[str, ...]:
    ending_id = state.final_result.ending_id
    if ending_id not in SURVIVAL_BODY_CANDIDATES:
        raise ValueError("survival text selection requires a completed ending")
    if state.population.population_dead > 0:
        return SURVIVAL_BODY_CANDIDATES[ending_id]
    safe_without_deaths = {
        "high_victory": ("ending.high_victory.body.02",),
        "standard_victory": ("ending.standard_victory.body.03",),
        "bitter_victory": ("ending.bitter_victory.body.04",),
        "collapse_survival": (
            "ending.collapse_survival.body.01",
            "ending.collapse_survival.body.03",
        ),
        "ember_survival": (
            "ending.ember_survival.body.01",
            "ending.ember_survival.body.02",
        ),
    }
    return safe_without_deaths[ending_id]


def _death_record_text_id(state: GameState) -> str:
    if state.population.population_dead == 0:
        return "ending.report.death_record.none"
    if state.social_policy.unhandled_bodies > 0:
        return "ending.report.death_record.unhandled"
    if state.social_policy.death_path == "cemetery":
        return "ending.report.death_record.cemetery"
    if state.social_policy.death_path == "cold_pit":
        return "ending.report.death_record.cold_pit"
    if "ember_roster" in state.oath_order.signed_law_ids:
        return "ending.report.death_record.ember_roster"
    return "ending.report.death_record.unhandled"


def _hard_fail_body_candidates(state: GameState) -> tuple[str, ...]:
    hard_fail = state.final_result.hard_fail_type
    if hard_fail is None:
        raise ValueError("hard-fail text selection requires a hard-fail type")
    candidates = list(HARD_FAIL_BODY_CANDIDATES[hard_fail.value])
    day = state.calendar.current_day
    if hard_fail.value == "core_collapse":
        candidates.remove("ending.hard_fail.core_collapse.body.03")
    if hard_fail.value == "population_zero" and day < 49:
        candidates.remove("ending.hard_fail.population_zero.body.04")
    if hard_fail.value == "core_collapse" and day >= 49:
        candidates.remove("ending.hard_fail.core_collapse.body.04")
    if hard_fail.value == "panic_expelled" and day < 49:
        candidates.remove("ending.hard_fail.panic_expelled.body.04")
    return tuple(candidates)


def _legacy_illness_text_id(state: GameState) -> str | None:
    sick_total = (
        state.population.sick_population
        + state.population.critical_population
    )
    score = state.final_result.system_scores.get("medical_and_disease", 0)
    has_medical = any(
        _has_building(state, building_type)
        for building_type in ("medical_station", "hospital")
    )
    if sick_total == 0:
        return "ending.report.illness.03" if has_medical else None
    if not has_medical:
        return None
    if score <= 1:
        return "ending.report.illness.04"
    return "ending.report.illness.01"


def _final_day_service_record(state: GameState) -> object | None:
    record = state.final_frost.daily_records.get(str(state.calendar.max_day))
    if record is None or not getattr(record, "service_history_known", False):
        return None
    return record


def _patch027_illness_text_id(state: GameState) -> str | None:
    sick_total = (
        state.population.sick_population
        + state.population.critical_population
    )
    record = _final_day_service_record(state)
    has_operational_medical_service = bool(
        record is not None
        and getattr(record, "medical_operational_building_count", 0) > 0
        and getattr(record, "medical_building_capacity", 0) > 0
    )
    if not has_operational_medical_service:
        return None
    if sick_total == 0:
        return "ending.report.illness.03"
    score = state.final_result.system_scores.get("medical_and_disease", 0)
    if score <= 1:
        return "ending.report.illness.04"
    return "ending.report.illness.01"


def _illness_text_id(state: GameState) -> str | None:
    sick_total = (
        state.population.sick_population
        + state.population.critical_population
    )
    record = _final_day_service_record(state)
    patch027_text_id = _patch027_illness_text_id(state)
    if sick_total > 0 and record is not None and patch027_text_id is None:
        return "ending.report.illness.no_service"
    return patch027_text_id


def _score_text_id(prefix: str, score: int) -> str:
    index = 1 if score >= 4 else 2 if score == 3 else 3 if score == 2 else 4
    return f"ending.report.{prefix}.{index:02d}"


def _legacy_coal_food_text_id(state: GameState) -> str:
    score = min(
        state.final_result.system_scores.get("coal_and_core", 0),
        state.final_result.system_scores.get("food", 0),
    )
    index = 3 if score >= 3 else 2 if score == 2 else 1
    return f"ending.report.coal_food.{index:02d}"


def _patch027_coal_food_text_id(state: GameState) -> str | None:
    food_total = state.resources.raw_food + state.resources.cooked_food
    if state.resources.coal <= 0 or food_total <= 0:
        return None
    return _legacy_coal_food_text_id(state)


def _coal_food_text_id(state: GameState) -> str:
    food_total = state.resources.raw_food + state.resources.cooked_food
    coal_empty = state.resources.coal <= 0
    food_empty = food_total <= 0
    if coal_empty and food_empty:
        return "ending.report.coal_food.both_empty"
    if coal_empty:
        return "ending.report.coal_food.coal_empty"
    if food_empty:
        return "ending.report.coal_food.food_empty"
    return _legacy_coal_food_text_id(state)


def _additional_text_ids(state: GameState) -> list[str]:
    ending_id = state.final_result.ending_id
    if ending_id not in _ADDITIONAL_LIMITS:
        return []
    ordered_tags = [
        *state.final_result.defining_tags,
        *state.final_result.major_tags,
    ]
    topics: list[str] = []
    for tag in ordered_tags:
        for topic, matching_tags in _ADDITIONAL_TOPICS.items():
            if (
                tag in matching_tags
                and topic not in topics
                and not (
                    topic == "death"
                    and state.population.population_dead == 0
                )
            ):
                topics.append(topic)
                break
    limit = _ADDITIONAL_LIMITS[ending_id]
    selected: list[str] = []
    records = tuple(state.final_frost.daily_records.values())
    has_active_doctor_and_medical_apprentice = any(
        building.building_type in {"medical_station", "hospital"}
        and building.is_built
        and building.is_operational
        and building.assigned_engineers > 0
        and building.assigned_medical_apprentices > 0
        for building in state.buildings.values()
    )
    for topic in topics:
        candidates = list(ADDITIONAL_CANDIDATES[topic])
        if topic == "death":
            candidates = [
                "ending.additional.death.01",
                "ending.additional.death.02",
            ]
            if state.final_frost.frost_deaths > 0:
                candidates.append("ending.additional.death.03")
        if topic == "medical":
            candidates = []
            if any(
                _medical_history_proves_first_candidate(record)
                for record in records
            ):
                candidates.append("ending.additional.medical.01")
            if any(
                _medical_history_proves_second_candidate(record)
                for record in records
            ):
                candidates.append("ending.additional.medical.02")
            if has_active_doctor_and_medical_apprentice:
                candidates.append("ending.additional.medical.03")
            if not candidates:
                continue
        if topic == "food":
            candidates = []
            if _canteen_history_is_proven(state):
                candidates.append("ending.additional.food.01")
            candidates.append("ending.additional.food.02")
        if topic == "core":
            candidates = []
            if any(item.overload_redline for item in records):
                candidates.append("ending.additional.core.01")
            if any(item.heating_shortfall for item in records):
                candidates.append("ending.additional.core.02")
            if any(item.overload_used for item in records):
                candidates.append("ending.additional.core.03")
            if not candidates:
                continue
        selected.append(
            _choose(state, f"additional.{topic}", tuple(candidates))
        )
        if len(selected) == limit:
            break
    return selected


def _trace_text_ids(state: GameState) -> list[str]:
    ordinary_laws = set(state.laws.signed_law_ids)
    route_laws = set(state.oath_order.signed_law_ids)
    route_actions = set(state.oath_order.action_last_used_day)
    child_trace: str | None = None
    if ordinary_laws & {
        "child_labor_low_risk_law",
        "child_labor_all_jobs_law",
    } and any(
        building.assigned_children > 0
        for building in state.buildings.values()
    ):
        child_trace = "ending.trace.child_labor"
    route_trace: str | None = None
    if {
        "guard_oath",
        "mourning_bell",
        "shared_meal",
        "ember_roster",
    } <= route_laws and {"guard_oath", "mourning_bell", "shared_meal"} <= route_actions:
        route_trace = "ending.trace.oath_route"
    elif (
        state.population.population_dead > 0
        and "ember_roster" in route_laws
    ):
        route_trace = "ending.report.death_record.ember_roster"
    elif {
        "city_patrol_order",
        "morning_roll_call",
        "unified_announcement",
        "temporary_detain",
    } <= route_laws and {"patrol", "announcement", "detain"} <= route_actions:
        route_trace = "ending.trace.iron_route"

    if child_trace is not None and route_trace is not None:
        return [child_trace, route_trace]
    if child_trace is not None:
        return [child_trace]
    if route_trace is not None:
        return [route_trace]
    if state.old_city.actual_departures > 0:
        return ["ending.trace.old_city"]
    tags = set(state.final_result.ending_tags)
    if "sedation_city" not in tags and (
        _has_operational_building(state, "small_tavern")
        or _has_operational_building(state, "grand_casino")
        or state.social_policy.firepit_enabled
    ):
        return ["ending.trace.entertainment"]
    return []


def _route_full_text_id(state: GameState) -> str | None:
    route_laws = set(state.oath_order.signed_law_ids)
    if state.oath_order.final_oath_active or "final_oath" in route_laws:
        return "ending.route.final_oath.full_text"
    if state.oath_order.highest_order_active or "highest_order" in route_laws:
        return "ending.route.final_decree.full_text"
    if state.oath_order.selected_route == "oath":
        return "ending.route.oath.full_text"
    if state.oath_order.selected_route == "iron":
        return "ending.route.iron.full_text"
    return None


def _old_city_full_text_ids(state: GameState) -> list[str]:
    old = state.old_city
    if not old.is_unlocked:
        return []
    selected: list[str] = []
    if old.result_id in {"partial_exodus", "large_exodus"}:
        has_departures = old.actual_departures > 0
        has_resource_losses = any(
            loss > 0 for loss in old.settlement_resource_losses.values()
        )
        if has_departures and has_resource_losses:
            selected.append(_OLD_CITY_FULL_TEXT_IDS[old.result_id])
    else:
        selected.append(
            _OLD_CITY_FULL_TEXT_IDS.get(
                old.result_id,
                "ending.old_city.unresolved.full_text",
            )
        )
    if old.promise_settled and old.promise_outcome in _OLD_CITY_PROMISE_TEXT_IDS:
        selected.append(_OLD_CITY_PROMISE_TEXT_IDS[old.promise_outcome])
    return selected


def _old_city_full_text_is_pending(state: GameState) -> bool:
    old = state.old_city
    if not old.is_unlocked or old.result_id not in {
        "partial_exodus",
        "large_exodus",
    }:
        return False
    return old.actual_departures <= 0 or not any(
        loss > 0 for loss in old.settlement_resource_losses.values()
    )


def _children_full_text_id(state: GameState) -> str | None:
    ordinary_laws = set(state.laws.signed_law_ids)
    if "child_labor_all_jobs_law" in ordinary_laws:
        return "ending.children.labor_all_jobs.full_text"
    if "child_labor_low_risk_law" in ordinary_laws:
        return "ending.children.labor_low_risk.full_text"
    if "child_protection_law" not in ordinary_laws:
        return None
    has_shelter = _has_building(state, "child_shelter")
    has_school = _has_building(state, "school")
    if not has_shelter:
        return "ending.children.protection.no_shelter.full_text"
    if not has_school:
        return "ending.children.protection.shelter_only.full_text"
    if "medical_apprentices_law" in ordinary_laws:
        return "ending.children.protection.medical_track.full_text"
    if "engineering_apprentices_law" in ordinary_laws:
        return "ending.children.protection.engineering_track.full_text"
    return "ending.children.protection.school.full_text"


def _entertainment_full_text_id(state: GameState) -> str | None:
    ordinary_laws = set(state.laws.signed_law_ids)
    if not ordinary_laws & {"tavern_law", "casino_law"}:
        return None
    if _has_operational_building(state, "grand_casino"):
        return "ending.entertainment.casino.full_text"
    if _has_operational_building(state, "small_tavern"):
        return "ending.entertainment.tavern.full_text"
    return "ending.entertainment.no_operational_facility.full_text"


def _patch030_full_text_ids(state: GameState) -> list[str]:
    selected: list[str] = []
    route_text_id = _route_full_text_id(state)
    if route_text_id is not None:
        selected.append(route_text_id)
    selected.extend(_old_city_full_text_ids(state))
    children_text_id = _children_full_text_id(state)
    if children_text_id is not None:
        selected.append(children_text_id)
    entertainment_text_id = _entertainment_full_text_id(state)
    if entertainment_text_id is not None:
        selected.append(entertainment_text_id)
    return selected


def _patch030_trace_text_ids(state: GameState) -> list[str]:
    replaced: set[str] = set()
    if _children_full_text_id(state) is not None:
        replaced.update(_PATCH_030_REPLACED_TRACE_TEXT_IDS["children"])
    if _route_full_text_id(state) is not None:
        replaced.update(_PATCH_030_REPLACED_TRACE_TEXT_IDS["route"])
    if _old_city_full_text_ids(state):
        replaced.update(_PATCH_030_REPLACED_TRACE_TEXT_IDS["old_city"])
    if _entertainment_full_text_id(state) is not None:
        replaced.update(_PATCH_030_REPLACED_TRACE_TEXT_IDS["entertainment"])
    return [text_id for text_id in _trace_text_ids(state) if text_id not in replaced]


def _report_body_text_ids(
    state: GameState,
    *,
    patch020_fact_contract: bool,
    patch027_fact_contract: bool = False,
    patch030_text_contract: bool = False,
) -> list[str]:
    final = state.final_result
    if final.run_state is RunState.ENDED:
        return [
            "ending.player_ended.status",
            _choose(
                state,
                "player_ended.body",
                PLAYER_ENDED_BODY_CANDIDATES,
            ),
            "ending.player_ended.closing",
        ]
    if final.hard_fail_type is not None:
        hard_fail = final.hard_fail_type.value
        return [
            f"ending.hard_fail.{hard_fail}.reason",
            _choose(
                state,
                f"hard_fail.{hard_fail}.body",
                _hard_fail_body_candidates(state),
            ),
            _death_record_text_id(state),
            _choose(
                state,
                "hard_fail.closing",
                HARD_FAIL_CLOSING_CANDIDATES,
            ),
        ]
    ending_id = final.ending_id
    if ending_id not in SURVIVAL_BODY_CANDIDATES:
        raise ValueError("survival text selection requires a completed ending")
    body = [
        _choose(
            state,
            f"survival.{ending_id}.body",
            _survival_body_candidates(state),
        ),
        "ending.report.opening",
        _death_record_text_id(state),
    ]
    if state.final_frost.frost_deaths > 0:
        body.append("ending.report.frostfall_deaths")
    if patch020_fact_contract:
        illness_text_id = _legacy_illness_text_id(state)
    elif patch027_fact_contract:
        illness_text_id = _patch027_illness_text_id(state)
    else:
        illness_text_id = _illness_text_id(state)
    if illness_text_id is not None:
        body.append(illness_text_id)
    body.extend(
        (
            _score_text_id(
                "trust_panic",
                final.system_scores.get("trust_and_panic", 0),
            ),
            _score_text_id(
                "core", final.system_scores.get("coal_and_core", 0)
            ),
        )
    )
    if patch020_fact_contract:
        coal_food_text_id = _legacy_coal_food_text_id(state)
    elif patch027_fact_contract:
        coal_food_text_id = _patch027_coal_food_text_id(state)
    else:
        coal_food_text_id = _coal_food_text_id(state)
    if coal_food_text_id is not None:
        body.append(coal_food_text_id)
    body.append(_choose(state, "report.future", REPORT_FUTURE_CANDIDATES))
    body.extend(_additional_text_ids(state))
    if patch030_text_contract:
        body.extend(_patch030_trace_text_ids(state))
        body.extend(_patch030_full_text_ids(state))
    else:
        body.extend(_trace_text_ids(state))
    body.append(
        _choose(
            state,
            f"interrogation.{ending_id}",
            INTERROGATION_CANDIDATES[ending_id],
        )
    )
    return body


def canonical_report_body_text_ids(state: GameState) -> list[str]:
    return _report_body_text_ids(
        state,
        patch020_fact_contract=False,
        patch030_text_contract=True,
    )


def patch030_report_body_text_ids(state: GameState) -> list[str]:
    """Reproduce report format 5 without rewriting existing saved reports."""

    return _report_body_text_ids(
        state,
        patch020_fact_contract=False,
        patch030_text_contract=True,
    )


def patch029_report_body_text_ids(state: GameState) -> list[str]:
    """Reproduce report format 4 without rewriting existing saved reports."""

    return _report_body_text_ids(state, patch020_fact_contract=False)


def patch020_report_body_text_ids(state: GameState) -> list[str]:
    """Reproduce report format 2 without rewriting existing saved reports."""

    return _report_body_text_ids(state, patch020_fact_contract=True)


def patch027_report_body_text_ids(state: GameState) -> list[str]:
    """Reproduce report format 3 without rewriting existing saved reports."""

    return _report_body_text_ids(
        state,
        patch020_fact_contract=False,
        patch027_fact_contract=True,
    )


def canonical_report_title_text_id(state: GameState) -> str:
    final = state.final_result
    if final.run_state is RunState.ENDED:
        return ENDING_TITLE_TEXT_IDS["player_ended"]
    if final.hard_fail_type is not None:
        return f"ending.hard_fail.{final.hard_fail_type.value}.title"
    if final.ending_id is None:
        raise ValueError("ending title selection requires a completed ending")
    return ENDING_TITLE_TEXT_IDS[final.ending_id]


def _report_pending_text_ids(
    state: GameState,
    *,
    patch020_fact_contract: bool,
    patch027_fact_contract: bool = False,
    patch030_text_contract: bool = False,
    sedation_pending_requires_tag: bool = False,
) -> list[str]:
    pending: set[str] = set()
    ordinary_laws = set(state.laws.signed_law_ids)
    route_laws = set(state.oath_order.signed_law_ids)
    ending_tags = {
        *state.final_result.defining_tags,
        *state.final_result.major_tags,
        *state.final_result.ending_tags,
    }
    if (
        (patch027_fact_contract or not patch020_fact_contract)
        and _uses_survival_report(state)
        and final_result_requires_illness_text(state)
    ):
        selected_illness_text_id = (
            _patch027_illness_text_id(state)
            if patch027_fact_contract
            else _illness_text_id(state)
        )
        if selected_illness_text_id is None:
            pending.add(_PENDING_REPORT_ILLNESS_TEXT_ID)
    if (
        patch027_fact_contract
        and _uses_survival_report(state)
        and _patch027_coal_food_text_id(state) is None
    ):
        pending.add(_PENDING_REPORT_COAL_FOOD_TEXT_ID)
    if ending_tags & _ADDITIONAL_TOPICS["medical"]:
        records = tuple(state.final_frost.daily_records.values())
        if any(not record.service_history_known for record in records):
            if not any(
                _medical_history_proves_first_candidate(record)
                for record in records
            ):
                pending.add(_PENDING_MEDICAL_TEXT_IDS[0])
            if not any(
                _medical_history_proves_second_candidate(record)
                for record in records
            ):
                pending.add(_PENDING_MEDICAL_TEXT_IDS[1])
    if ending_tags & _ADDITIONAL_TOPICS["food"]:
        records = tuple(state.final_frost.daily_records.values())
        if (
            any(not record.service_history_known for record in records)
            and not _canteen_history_is_proven(state)
        ):
            pending.add(_PENDING_FOOD_TEXT_ID)
    if not patch030_text_contract:
        if ordinary_laws & {
            "child_labor_low_risk_law",
            "child_labor_all_jobs_law",
            "child_protection_law",
        }:
            pending.add(_PENDING_LONG_TEXT_IDS["children"])
        if (
            "child_protection_law" in ordinary_laws
            and "child_school_law" in ordinary_laws
            and _has_building(state, "child_shelter")
            and _has_building(state, "school")
        ):
            pending.add(_PENDING_LONG_TEXT_IDS["children_trace"])
        if state.population.population_dead > 0:
            pending.add(_PENDING_LONG_TEXT_IDS["death"])
        if ordinary_laws & {"tavern_law", "casino_law"}:
            pending.add(_PENDING_LONG_TEXT_IDS["entertainment"])
        if state.oath_order.selected_route == "oath":
            pending.add(_PENDING_LONG_TEXT_IDS["oath"])
        if state.oath_order.selected_route == "iron":
            pending.add(_PENDING_LONG_TEXT_IDS["iron"])
        if state.oath_order.final_oath_active or "final_oath" in route_laws:
            pending.add(_PENDING_LONG_TEXT_IDS["final_oath"])
        if state.oath_order.highest_order_active or "highest_order" in route_laws:
            pending.add(_PENDING_LONG_TEXT_IDS["final_decree"])
        if state.old_city.is_unlocked:
            pending.add(_PENDING_LONG_TEXT_IDS["old_city"])
    else:
        if _old_city_full_text_is_pending(state):
            pending.add(_PENDING_LONG_TEXT_IDS["old_city"])
        sedation_pending_applies = (
            "sedation_city" in ending_tags
            if sedation_pending_requires_tag
            else bool(ordinary_laws & {"tavern_law", "casino_law"})
        )
        if sedation_pending_applies:
            pending.add("ending.entertainment.sedation_city.full_text")
    return sorted(pending)


def _uses_survival_report(state: GameState) -> bool:
    return (
        state.final_result.hard_fail_type is None
        and state.final_result.ending_id in SURVIVAL_BODY_CANDIDATES
        and state.final_result.run_state is not RunState.ENDED
    )


def final_result_requires_illness_text(state: GameState) -> bool:
    return (
        _uses_survival_report(state)
        and (
            state.population.sick_population
            + state.population.critical_population
            > 0
        )
    )


def canonical_report_pending_text_ids(state: GameState) -> list[str]:
    return _report_pending_text_ids(
        state,
        patch020_fact_contract=False,
        patch030_text_contract=True,
        sedation_pending_requires_tag=True,
    )


def patch030_report_pending_text_ids(state: GameState) -> list[str]:
    """Reproduce report format 5 without rewriting existing saved reports."""

    return _report_pending_text_ids(
        state,
        patch020_fact_contract=False,
        patch030_text_contract=True,
    )


def patch029_report_pending_text_ids(state: GameState) -> list[str]:
    """Return the exact pending set used by report format 4."""

    return _report_pending_text_ids(state, patch020_fact_contract=False)


def patch020_report_pending_text_ids(state: GameState) -> list[str]:
    """Reproduce the exact pending set used by report format 2."""

    return _report_pending_text_ids(state, patch020_fact_contract=True)


def patch027_report_pending_text_ids(state: GameState) -> list[str]:
    """Return the exact pending set used by report format 3."""

    return _report_pending_text_ids(
        state,
        patch020_fact_contract=False,
        patch027_fact_contract=True,
    )


def legacy_report_pending_text_ids(state: GameState) -> list[str]:
    """Return the exact Patch 010 pending set accepted for old v14 saves."""

    final = state.final_result
    pending: set[str] = {ENDING_REPORT_DEATH_RECORD_TEXT_ID}
    if final.ending_id == "hard_fail":
        if final.hard_fail_type is not None:
            pending.add(
                ENDING_HARD_FAIL_BODY_POOL_TEXT_IDS[
                    final.hard_fail_type.value
                ]
            )
        pending.add("ending.hard_fail.closing_pool")
    else:
        pending.update(ENDING_REPORT_NARRATIVE_POOL_TEXT_IDS)
        if final.ending_id is not None:
            pending.add(ENDING_BODY_POOL_TEXT_IDS[final.ending_id])
            interrogation = ENDING_INTERROGATION_POOL_BY_ENDING.get(
                final.ending_id
            )
            if interrogation is not None:
                pending.add(interrogation)
        tags = set(final.major_tags) | set(final.defining_tags)
        for text_id, matching_tags in ENDING_ADDITIONAL_POOL_TAGS.items():
            if tags & matching_tags:
                pending.add(text_id)
    if final.run_state is RunState.ENDED:
        pending.add(ENDING_BODY_POOL_TEXT_IDS["player_ended"])
    if state.final_frost.frost_deaths == 0:
        pending.add(ENDING_REPORT_ZERO_FROST_DEATHS_TEXT_ID)
    return sorted(pending)


def report_template_values(state: GameState) -> dict[str, int]:
    arrival_population = sum(
        item.population_added for item in state.events.resolution_history
    )
    return {
        "start_population": (
            state.population.population_total_ever - arrival_population
        ),
        "total_deaths": state.population.population_dead,
        "unhandled_bodies": state.social_policy.unhandled_bodies,
        "frostfall_deaths": state.final_frost.frost_deaths,
        "sick_total": (
            state.population.sick_population
            + state.population.critical_population
        ),
        "actual_departures": state.old_city.actual_departures,
    }
