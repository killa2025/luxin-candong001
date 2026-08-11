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


def _illness_text_id(state: GameState) -> str | None:
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


def _score_text_id(prefix: str, score: int) -> str:
    index = 1 if score >= 4 else 2 if score == 3 else 3 if score == 2 else 4
    return f"ending.report.{prefix}.{index:02d}"


def _coal_food_text_id(state: GameState) -> str:
    score = min(
        state.final_result.system_scores.get("coal_and_core", 0),
        state.final_result.system_scores.get("food", 0),
    )
    index = 3 if score >= 3 else 2 if score == 2 else 1
    return f"ending.report.coal_food.{index:02d}"


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
    disease_deaths = sum(item.actual_disease_deaths for item in records)
    has_medical = any(
        _has_building(state, building_type)
        for building_type in ("medical_station", "hospital")
    )
    has_active_medical_apprentice = any(
        building.building_type in {"medical_station", "hospital"}
        and building.is_built
        and building.is_operational
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
            if (
                has_medical
                and disease_deaths > 0
                and any(not item.hospital_shutdown for item in records)
            ):
                candidates.append("ending.additional.medical.01")
            if (
                has_medical
                and disease_deaths > 0
                and any(item.medical_overflow for item in records)
            ):
                candidates.append("ending.additional.medical.02")
            if has_active_medical_apprentice:
                candidates.append("ending.additional.medical.03")
            if not candidates:
                continue
        if topic == "food":
            candidates.remove("ending.additional.food.03")
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


def canonical_report_body_text_ids(state: GameState) -> list[str]:
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
            _coal_food_text_id(state),
            _choose(state, "report.future", REPORT_FUTURE_CANDIDATES),
        )
    )
    body.extend(_additional_text_ids(state))
    body.extend(_trace_text_ids(state))
    body.append(
        _choose(
            state,
            f"interrogation.{ending_id}",
            INTERROGATION_CANDIDATES[ending_id],
        )
    )
    return body


def canonical_report_title_text_id(state: GameState) -> str:
    final = state.final_result
    if final.run_state is RunState.ENDED:
        return ENDING_TITLE_TEXT_IDS["player_ended"]
    if final.hard_fail_type is not None:
        return f"ending.hard_fail.{final.hard_fail_type.value}.title"
    if final.ending_id is None:
        raise ValueError("ending title selection requires a completed ending")
    return ENDING_TITLE_TEXT_IDS[final.ending_id]


def canonical_report_pending_text_ids(state: GameState) -> list[str]:
    pending: set[str] = set()
    ordinary_laws = set(state.laws.signed_law_ids)
    route_laws = set(state.oath_order.signed_law_ids)
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
    return sorted(pending)


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
    }
