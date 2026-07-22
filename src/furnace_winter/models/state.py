from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from furnace_winter.models.randomness import RandomState


CURRENT_SAVE_DATA_VERSION = 7
FINAL_DAY = 55
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
    """Population-pool hunger tiers.

    Patch 003 establishes the machine-readable pools. Their day-to-day
    progression and recovery timing remain pending balance rules.
    """

    mild_population: int = 0
    severe_population: int = 0
    starving_population: int = 0


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
class EventState:
    active_event_ids: list[str] = field(default_factory=list)
    resolved_event_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromiseState:
    active_promise_ids: list[str] = field(default_factory=list)
    completed_promise_ids: list[str] = field(default_factory=list)
    failed_promise_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OldCityState:
    is_unlocked: bool = False
    active_stage_id: str | None = None


@dataclass(slots=True)
class FinalResultState:
    is_finalized: bool = False
    ending_id: str | None = None
    hard_fail_type: HardFailType | None = None
    ending_tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.hard_fail_type is not None and not isinstance(
            self.hard_fail_type, HardFailType
        ):
            raise TypeError("hard_fail_type must be HardFailType or None")


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
    daily_survival: DailySurvivalState = field(default_factory=DailySurvivalState)
    trust_panic: TrustPanicState = field(default_factory=TrustPanicState)
    furnace: FurnaceState = field(default_factory=FurnaceState)
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
    final_result: FinalResultState = field(default_factory=FinalResultState)

    @classmethod
    def initial(cls, random_seed: int = 0) -> GameState:
        return cls(random=RandomState.initial(random_seed))
