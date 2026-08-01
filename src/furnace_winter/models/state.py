from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from furnace_winter.models.randomness import RandomState


CURRENT_SAVE_DATA_VERSION = 14
FINAL_DAY = 55
ENDING_TITLE_TEXT_IDS = {
    "hard_fail": "ending.title.hard_fail",
    "high_victory": "ending.title.high_victory",
    "standard_victory": "ending.title.standard_victory",
    "bitter_victory": "ending.title.bitter_victory",
    "collapse_survival": "ending.title.collapse_survival",
    "ember_survival": "ending.title.ember_survival",
    "player_ended": "ending.title.player_ended",
}
ENDING_BODY_POOL_TEXT_IDS = {
    "high_victory": "ending.high_victory.body_pool",
    "standard_victory": "ending.standard_victory.body_pool",
    "bitter_victory": "ending.bitter_victory.body_pool",
    "collapse_survival": "ending.collapse_survival.body_pool",
    "ember_survival": "ending.ember_survival.body_pool",
    "player_ended": "ending.player_ended.body_pool",
}
ENDING_HARD_FAIL_BODY_POOL_TEXT_IDS = {
    "population_zero": "ending.hard_fail.population_zero.body_pool",
    "core_collapse": "ending.hard_fail.core_collapse.body_pool",
    "trust_exile": "ending.hard_fail.trust_exile.body_pool",
    "panic_expelled": "ending.hard_fail.panic_expelled.body_pool",
}
ENDING_HARD_FAIL_REASON_TEXT_IDS = {
    "population_zero": "ending.hard_fail.population_zero.reason",
    "core_collapse": "ending.hard_fail.core_collapse.reason",
    "trust_exile": "ending.hard_fail.trust_exile.reason",
    "panic_expelled": "ending.hard_fail.panic_expelled.reason",
}
ENDING_REPORT_NARRATIVE_POOL_TEXT_IDS = (
    "ending.report.illness.pool",
    "ending.report.trust_panic.pool",
    "ending.report.core.pool",
    "ending.report.coal_food.pool",
    "ending.report.future.pool",
)
ENDING_REPORT_DEATH_RECORD_TEXT_ID = "ending.report.death_record_sentence"
ENDING_REPORT_ZERO_FROST_DEATHS_TEXT_ID = (
    "ending.report.frostfall_deaths.zero_sentence"
)
ENDING_PLAYER_ENDED_BODY_TEXT_IDS = (
    "ending.player_ended.status",
    "ending.player_ended.closing",
)
ENDING_INTERROGATION_POOL_BY_ENDING = {
    "high_victory": "ending.interrogation.high_victory.pool",
    "standard_victory": "ending.interrogation.general.pool",
    "bitter_victory": "ending.interrogation.cost.pool",
    "collapse_survival": "ending.interrogation.cost.pool",
    "ember_survival": "ending.interrogation.ember.pool",
}
ENDING_ADDITIONAL_POOL_TAGS = {
    "ending.additional.death.pool": {
        "mass_death",
        "grave_city",
        "frost_survived_broken",
    },
    "ending.additional.medical.pool": {
        "medical_strained",
        "medical_collapse",
        "silent_hospital",
        "survived_with_disabled",
    },
    "ending.additional.food.pool": {
        "famine_survivor",
        "famine_city",
    },
    "ending.additional.core.pool": {
        "coal_desperate",
        "cold_engine",
        "redline_survivor",
        "overload_burned_city",
        "heat_last_stand",
    },
    "ending.additional.society.pool": {
        "broken_society",
        "oath_carried_zero_trust",
        "decree_carried_panic",
    },
    "ending.additional.housing.pool": {
        "cold_houses",
        "frozen_homeless",
        "city_continuity_broken",
    },
}
OVERTIME_BUILDING_TYPES = frozenset({
    "medical_station",
    "hospital",
    "research_institute",
    "canteen",
    "greenhouse",
    "improved_greenhouse",
    "small_coal_miner",
    "small_steel_miner",
    "large_coal_miner",
    "large_steel_miner",
    "logging_camp",
})


class HardFailType(StrEnum):
    POPULATION_ZERO = "population_zero"
    CORE_COLLAPSE = "core_collapse"
    TRUST_EXILE = "trust_exile"
    PANIC_EXPELLED = "panic_expelled"


class RunState(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class TerminationReason(StrEnum):
    PLAYER_ENDED = "player_ended"


@dataclass(slots=True)
class CalendarState:
    current_day: int = 1
    max_day: int = FINAL_DAY
    current_phase: str | None = None
    is_day_locked: bool = False
    is_end_day_confirmed: bool = False


@dataclass(slots=True)
class PopulationState:
    population_total: int = 0
    population_total_ever: int = 0
    population_alive: int = 0
    population_dead: int = 0
    workers: int = 0
    engineers: int = 0
    children: int = 0
    medical_apprentices: int = 0
    engineering_apprentices: int = 0
    disabled_population: int = 0
    healthy_population: int = 0
    sick_population: int = 0
    critical_population: int = 0
    homeless_population: int = 0
    housed_population: int = 0


@dataclass(slots=True)
class ResourceState:
    coal: int = 0
    wood: int = 0
    steel: int = 0
    raw_food: int = 0
    cooked_food: int = 0
    storage_capacity: int = 0


@dataclass(slots=True)
class HousingState:
    """Aggregate housing only; residents are not assigned to individual homes."""

    basic_residences: int = 0
    capacity: int = 0


@dataclass(slots=True)
class HungerState:
    """Patch 013 deterministic hunger overlay and integer remainders."""

    none_population: int = 0
    light_population: int = 0
    severe_population: int = 0
    starving_population: int = 0
    illness_remainder: int = 0
    severe_remainder: int = 0
    death_remainder: int = 0
    trust_remainder: int = 0
    panic_remainder: int = 0
    total_hunger_days: int = 0
    total_unfed_person_days: int = 0
    peak_unfed_count: int = 0
    peak_unfed_population_start: int = 0
    hunger_deaths_total: int = 0


@dataclass(slots=True)
class ColdExposureState:
    """Saved integer remainders for deterministic repeated cold exposure."""

    housed_disability_remainders: dict[str, int] = field(default_factory=dict)
    homeless_disability_remainders: dict[str, int] = field(default_factory=dict)
    housed_death_remainders: dict[str, int] = field(default_factory=dict)
    homeless_death_remainders: dict[str, int] = field(default_factory=dict)
    housed_level_streaks: dict[str, int] = field(default_factory=dict)
    homeless_level_streaks: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class DailySurvivalState:
    """Last settled day's deterministic resource and heating summary."""

    settled_day: int | None = None
    base_temperature: int | None = None
    target_furnace_level: int = 0
    effective_furnace_level: int = 0
    required_coal: int = 0
    coal_paid: int = 0
    woodfuel_wood_burned: int = 0
    woodfuel_contribution: int = 0
    target_overload_level: int = 0
    effective_overload_level: int = 0
    overload_coal_paid: int = 0
    overload_temperature_bonus: int = 0
    heating_shortfall: bool = False
    zone_temperatures: dict[str, int] = field(default_factory=dict)
    ration_mode_used: str = "normal"
    food_required: int = 0
    cooked_food_eaten: int = 0
    raw_food_eaten: int = 0
    food_shortfall: int = 0
    unfed_population: int = 0
    worktime_sick_added: int = 0
    overtime_accident_risk_points: int = 0
    storage_used: int = 0
    is_over_capacity: bool = False


@dataclass(slots=True)
class TrustPanicState:
    """Uninitialized until a later Patch loads confirmed starting values."""

    trust: int | None = None
    panic: int | None = None

    def __post_init__(self) -> None:
        for name, value in (("trust", self.trust), ("panic", self.panic)):
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer or None")
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")


@dataclass(slots=True)
class FurnaceState:
    is_active: bool = False
    mode_id: str = "off"
    pressure: int = 0
    overload_level: int = 0
    pressure_redline_warned: bool = False


@dataclass(slots=True)
class BuildingState:
    building_id: str
    building_type: str
    zone: str
    slot_size: int
    is_built: bool = False
    is_operational: bool = False
    assigned_workers: int = 0
    assigned_engineers: int = 0
    assigned_children: int = 0
    assigned_medical_apprentices: int = 0
    assigned_engineering_apprentices: int = 0
    can_heat: bool = False
    heated_today: bool = False
    effective_temperature: int = 0
    is_shutdown_by_temperature: bool = False
    bound_resource_id: str | None = None
    production_remainder_numerator: int = 0
    production_multiplier_remainder_numerator: int = 0
    production_multiplier_remainder_denominator: int = 1


@dataclass(slots=True)
class SurfaceResourcePointState:
    resource_point_id: str
    resource_type: str
    remaining_amount: int
    staff_capacity: int
    assigned_workers: int = 0
    assigned_engineers: int = 0
    production_remainder_numerator: int = 0
    is_depleted: bool = False


@dataclass(slots=True)
class BuildingManagementState:
    """Machine-readable building and map capacity state for Patch 004."""

    zone_slot_capacity: dict[str, int] = field(
        default_factory=lambda: {
            "inner_ring": 18,
            "middle_ring": 30,
            "outer_ring": 36,
            "storage_outer": 12,
        }
    )
    zone_slots_used: dict[str, int] = field(
        default_factory=lambda: {
            "inner_ring": 0,
            "middle_ring": 0,
            "outer_ring": 0,
            "storage_outer": 0,
        }
    )
    next_building_sequence: int = 1
    available_hunting_areas: int = 1
    total_hunting_areas: int = 2
    forest_zones: int = 2
    woodfuel_confirmed_today: bool = False
    heat_uses_today: int = 0


@dataclass(slots=True)
class LawState:
    signed_law_ids: list[str] = field(default_factory=list)
    active_law_ids: list[str] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class SocialPolicyState:
    """006A modes, one-day actions, and aggregate death handling state."""

    current_ration_mode: str = "normal"
    ration_food_numerator: int = 100
    ration_food_denominator: int = 100
    previous_ration_mode: str | None = None
    previous_ration_days: int = 0
    consecutive_ration_days: int = 0
    consecutive_ration_mode: str = "normal"
    current_worktime_mode: str = "normal"
    worktime_output_numerator: int = 100
    worktime_output_denominator: int = 100
    consecutive_long_shift_days: int = 0
    overtime_building_id: str | None = None
    overtime_output_numerator: int = 100
    overtime_output_denominator: int = 100
    firepit_enabled: bool = False
    death_path: str = "none"
    unhandled_bodies: int = 0
    buried_bodies: int = 0
    stored_bodies: int = 0
    triage_building_id: str | None = None
    triage_used_ever: bool = False
    ending_tag_candidates: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MedicalState:
    """Aggregate V1 medical capacity and deterministic action summaries."""

    temporary_capacity: int = 5
    building_capacity: int = 0
    effective_capacity: int = 5
    medical_pressure: int = 0
    sick_treatment_progress: int = 0
    critical_treatment_progress: int = 0
    medical_ration_sick_cured_today: int = 0
    medical_ration_critical_progress_today: int = 0


@dataclass(slots=True)
class TechState:
    researched_tech_ids: list[str] = field(default_factory=list)
    active_research_id: str | None = None
    research_progress_units: int = 0
    research_required_units: int = 0


@dataclass(slots=True)
class EventRecord:
    event_id: str
    event_type: str
    trigger_day: int
    priority: int
    instance_id: str
    occurrence_index: int
    trigger_reason_ids: list[str] = field(default_factory=list)
    option_ids: list[str] = field(default_factory=list)
    is_blocking: bool = False


@dataclass(slots=True)
class EventResolutionRecord:
    event_id: str
    option_id: str
    event_type: str
    resolved_day: int
    instance_id: str
    occurrence_index: int
    promise_id: str | None = None
    trust_change: int | None = None
    panic_change: int | None = None
    population_added: int = 0
    resource_changes: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class EventFollowupRecord:
    instance_id: str
    event_id: str
    option_id: str
    command_name: str
    created_day: int
    occurrence_index: int


@dataclass(slots=True)
class EventFollowupSettlementRecord:
    instance_id: str
    event_id: str
    option_id: str
    command_name: str
    created_day: int
    occurrence_index: int
    settled_day: int
    settled_command_sequence: int


@dataclass(slots=True)
class EventState:
    active_events: dict[str, EventRecord] = field(default_factory=dict)
    resolved_event_ids: list[str] = field(default_factory=list)
    resolution_history: list[EventResolutionRecord] = field(default_factory=list)
    occurrence_counts: dict[str, int] = field(default_factory=dict)
    cooldown_until_day: dict[str, int] = field(default_factory=dict)
    suppressed_event_ids_today: list[str] = field(default_factory=list)
    status_ids: list[str] = field(default_factory=list)
    generated_for_day: int | None = None
    metrics: dict[str, int] = field(default_factory=dict)
    recent_raw_food_days: list[int] = field(default_factory=list)
    recent_canteen_outage_days: list[int] = field(default_factory=list)
    recent_overtime_days: list[int] = field(default_factory=list)
    fixed_arrival_choices: dict[str, str] = field(default_factory=dict)
    fixed_arrival_pressure_days: dict[str, list[int]] = field(
        default_factory=dict
    )
    natural_death_overflow_candidates: dict[str, int] = field(
        default_factory=dict
    )
    pending_followups: dict[str, EventFollowupRecord] = field(default_factory=dict)
    consumed_followups: list[EventFollowupSettlementRecord] = field(
        default_factory=list
    )
    frostfall_warning_stage: str = "none"
    frostfall_eve_status_shown: bool = False
    seventh_frostfall_active: bool = False
    hidden_achievements_unlocked: list[str] = field(default_factory=list)
    hidden_achievement_popup_queue: list[str] = field(default_factory=list)
    cold_exposure_deaths_total: int = 0
    deaths_today_by_cause: dict[str, int] = field(default_factory=dict)

    @property
    def active_event_ids(self) -> list[str]:
        """Compatibility view for callers that only need stable event ids."""

        return list(self.active_events)


@dataclass(slots=True)
class PromiseRecord:
    promise_id: str
    promise_type: str
    source_event_id: str
    created_day: int
    deadline_day: int
    severity: str
    target: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class PromiseSettlementRecord:
    promise_id: str
    promise_type: str
    settled_day: int
    outcome: str
    severity: str
    trust_change: int
    panic_change: int


@dataclass(slots=True)
class PromiseState:
    active_promises: dict[str, PromiseRecord] = field(default_factory=dict)
    completed_promise_ids: list[str] = field(default_factory=list)
    failed_promise_ids: list[str] = field(default_factory=list)
    settlement_history: list[PromiseSettlementRecord] = field(default_factory=list)
    next_sequence: int = 1

    @property
    def active_promise_ids(self) -> list[str]:
        """Compatibility view for callers that only need stable promise ids."""

        return list(self.active_promises)


@dataclass(slots=True)
class OldCityState:
    is_unlocked: bool = False
    active_stage_id: str | None = None
    trigger_day: int = 24
    activation_pending: bool = False
    reference_population: int = 0
    member_count: int = 0
    low_threshold: int = 0
    middle_threshold: int = 0
    high_threshold: int = 0
    countdown_day: int | None = None
    resolved: bool = False
    result_id: str | None = None
    last_daily_trend: int = 0
    recent_major_death_days: list[int] = field(default_factory=list)
    stage_events_seen: list[str] = field(default_factory=list)
    pending_event_id: str | None = None
    hidden_growth_days_remaining: int = 0
    promise_active: bool = False
    promise_created_day: int | None = None
    promise_deadline_day: int | None = None
    promise_target_count: int | None = None
    promise_settled: bool = False
    promise_outcome: str | None = None
    promise_settled_day: int | None = None
    settlement_day: int | None = None
    settlement_member_count: int = 0
    theoretical_departures: int = 0
    actual_departures: int = 0
    protected_jobs: dict[str, int] = field(default_factory=dict)
    protected_engineers: int = 0
    reduction_reason: str | None = None
    settlement_resource_losses: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class RouteFacilityState:
    enabled: bool = False
    visible: bool = False
    assigned_workers: int = 0
    assigned_engineers: int = 0
    is_running: bool = False


@dataclass(slots=True)
class OathOrderState:
    page_unlocked: bool = False
    selected_route: str | None = None
    signed_law_ids: list[str] = field(default_factory=list)
    law_signed_days: dict[str, int] = field(default_factory=dict)
    next_law_day: int = 1
    oath_hall: RouteFacilityState = field(default_factory=RouteFacilityState)
    patrol_office: RouteFacilityState = field(default_factory=RouteFacilityState)
    action_next_available_day: dict[str, int] = field(default_factory=dict)
    action_last_used_day: dict[str, int] = field(default_factory=dict)
    final_oath_active: bool = False
    highest_order_active: bool = False
    death_panic_aftershock_halved_day: int | None = None
    ending_tag_candidates: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FrostDayRecord:
    day: int
    real_temperature: int
    display_label: str
    population_start: int
    population_end: int
    furnace_off: bool = False
    heating_shortfall: bool = False
    coal_shortage: bool = False
    furnace_underheated: bool = False
    overload_used: bool = False
    overload_redline: bool = False
    core_near_collapse: bool = False
    heat_uses: int = 0
    critical_building_frozen: bool = False
    cold_houses_population: int = 0
    cold_houses_day: bool = False
    homeless_exposure_population: int = 0
    mass_cold_exposure_population: int = 0
    mass_cold_exposure_day: bool = False
    food_shortage: bool = False
    starvation: bool = False
    unfed_population: int = 0
    medical_gap: int = 0
    medical_overflow: bool = False
    medical_collapse: bool = False
    hospital_shutdown: bool = False
    disease_spike: bool = False
    new_sick: int = 0
    new_critical: int = 0
    new_disabled: int = 0
    homeless_new_sick: int = 0
    homeless_new_disabled: int = 0
    homeless_cold_deaths: int = 0
    food_deaths: int = 0
    disease_deaths: int = 0
    cold_deaths: int = 0
    raw_disease_deaths: int = 0
    actual_disease_deaths: int = 0
    disease_death_overflow: int = 0
    raw_hunger_deaths: int = 0
    hunger_death_overflow: int = 0
    raw_cold_deaths: int = 0
    actual_cold_deaths: int = 0
    cold_death_overflow: int = 0
    base_natural_death_cap: int = 0
    applied_natural_death_cap: int = 0
    extreme_crisis_conditions: list[str] = field(default_factory=list)
    natural_death_overflow_pressure: int = 0
    mass_death: bool = False
    trust_crisis: bool = False
    panic_crisis: bool = False


@dataclass(slots=True)
class FinalFrostState:
    """D49-D55 facts used for deterministic scoring and later reports."""

    entered: bool = False
    baseline_day: int | None = None
    baseline_alive_population: int = 0
    baseline_healthy_population: int = 0
    baseline_sick_population: int = 0
    baseline_critical_population: int = 0
    baseline_disabled_population: int = 0
    baseline_workable_population: int = 0
    prepared_item_count: int = 0
    unprepared_item_count: int = 0
    preparation_tags: list[str] = field(default_factory=list)
    wood_supply_check_day: int | None = None
    wood_supply_surface_exhausted: bool = False
    wood_supply_logging_camp_available: bool = False
    wood_supply_wood_stock: int = 0
    wood_supply_logging_cost: int = 0
    wood_supply_alternative_available: bool = False
    wood_supply_legacy_exempt: bool = False
    wood_supply_locked: bool = False
    legacy_hunger_history_unknown: bool = False
    pending_extreme_crisis_conditions: list[str] = field(default_factory=list)
    daily_records: dict[str, FrostDayRecord] = field(default_factory=dict)
    frost_deaths: int = 0
    frost_hunger_days: int = 0
    frost_unfed_person_days: int = 0
    frost_population_person_days: int = 0
    frost_peak_unfed_count: int = 0
    frost_peak_population_start: int = 0
    frost_hunger_deaths: int = 0
    final_score_day: int | None = None


@dataclass(slots=True)
class EndingReportState:
    """Persisted text selections for the deterministic Patch 010 report."""

    is_generated: bool = False
    generated_day: int | None = None
    ending_state: str | None = None
    display_result_id: str | None = None
    title_text_id: str | None = None
    body_text_ids: list[str] = field(default_factory=list)
    pending_text_ids: list[str] = field(default_factory=list)
    hidden_achievement_ids: list[str] = field(default_factory=list)
    limiting_factor_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FinalResultState:
    is_finalized: bool = False
    ending_id: str | None = None
    hard_fail_type: HardFailType | None = None
    ending_tags: list[str] = field(default_factory=list)
    system_scores: dict[str, int] = field(default_factory=dict)
    total_score: int | None = None
    major_tags: list[str] = field(default_factory=list)
    defining_tags: list[str] = field(default_factory=list)
    run_state: RunState = RunState.ACTIVE
    termination_reason: TerminationReason | None = None
    termination_day: int | None = None
    termination_command_sequence: int | None = None
    report: EndingReportState = field(default_factory=EndingReportState)

    def __post_init__(self) -> None:
        if self.hard_fail_type is not None and not isinstance(
            self.hard_fail_type, HardFailType
        ):
            raise TypeError("hard_fail_type must be HardFailType or None")
        if not isinstance(self.run_state, RunState):
            raise TypeError("run_state must be RunState")
        if (
            self.termination_reason is not None
            and not isinstance(self.termination_reason, TerminationReason)
        ):
            raise TypeError(
                "termination_reason must be TerminationReason or None"
            )


@dataclass(slots=True)
class MapState:
    """Persisted map identity and the sealed resource-capacity summary."""

    map_key: str = "black_ash_lowland"
    selection_mode: str = "legacy_default"
    display_name_zh: str = "黑烬洼地"
    difficulty_zh: str = "标准"
    small_coal_piles: int = 4
    small_wood_piles: int = 5
    small_steel_piles: int = 3
    initial_hunting_grounds: int = 1
    total_hunting_grounds: int = 2
    forest_zones: int = 2
    large_coal_mine_points: int = 2
    large_steel_mine_points: int = 1


@dataclass(slots=True)
class GameState:
    save_data_version: int = CURRENT_SAVE_DATA_VERSION
    random: RandomState = field(default_factory=lambda: RandomState.initial(0))
    command_sequence: int = 0
    calendar: CalendarState = field(default_factory=CalendarState)
    population: PopulationState = field(default_factory=PopulationState)
    resources: ResourceState = field(default_factory=ResourceState)
    housing: HousingState = field(default_factory=HousingState)
    hunger: HungerState = field(default_factory=HungerState)
    cold_exposure: ColdExposureState = field(default_factory=ColdExposureState)
    daily_survival: DailySurvivalState = field(default_factory=DailySurvivalState)
    trust_panic: TrustPanicState = field(default_factory=TrustPanicState)
    furnace: FurnaceState = field(default_factory=FurnaceState)
    map: MapState = field(default_factory=MapState)
    buildings: dict[str, BuildingState] = field(default_factory=dict)
    surface_resource_points: dict[str, SurfaceResourcePointState] = field(
        default_factory=dict
    )
    building_management: BuildingManagementState = field(
        default_factory=BuildingManagementState
    )
    laws: LawState = field(default_factory=LawState)
    social_policy: SocialPolicyState = field(default_factory=SocialPolicyState)
    medical: MedicalState = field(default_factory=MedicalState)
    technologies: TechState = field(default_factory=TechState)
    events: EventState = field(default_factory=EventState)
    promises: PromiseState = field(default_factory=PromiseState)
    old_city: OldCityState = field(default_factory=OldCityState)
    oath_order: OathOrderState = field(default_factory=OathOrderState)
    final_frost: FinalFrostState = field(default_factory=FinalFrostState)
    final_result: FinalResultState = field(default_factory=FinalResultState)

    @classmethod
    def initial(cls, random_seed: int = 0) -> GameState:
        return cls(random=RandomState.initial(random_seed))
