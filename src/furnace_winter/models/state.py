from __future__ import annotations

from dataclasses import dataclass, field
from furnace_winter.models.randomness import RandomState


CURRENT_SAVE_DATA_VERSION = 1


@dataclass(slots=True)
class CalendarState:
    current_day: int = 1
    max_day: int = 55
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
class FurnaceState:
    is_active: bool = False
    mode_id: str | None = None
    pressure: int = 0


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


@dataclass(slots=True)
class LawState:
    signed_law_ids: list[str] = field(default_factory=list)
    active_law_ids: list[str] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class TechState:
    researched_tech_ids: list[str] = field(default_factory=list)
    active_research_id: str | None = None
    research_progress_days: int = 0


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
    hard_fail_type: str | None = None
    ending_tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GameState:
    save_data_version: int = CURRENT_SAVE_DATA_VERSION
    random: RandomState = field(default_factory=lambda: RandomState.initial(0))
    command_sequence: int = 0
    calendar: CalendarState = field(default_factory=CalendarState)
    population: PopulationState = field(default_factory=PopulationState)
    resources: ResourceState = field(default_factory=ResourceState)
    furnace: FurnaceState = field(default_factory=FurnaceState)
    buildings: dict[str, BuildingState] = field(default_factory=dict)
    laws: LawState = field(default_factory=LawState)
    technologies: TechState = field(default_factory=TechState)
    events: EventState = field(default_factory=EventState)
    promises: PromiseState = field(default_factory=PromiseState)
    old_city: OldCityState = field(default_factory=OldCityState)
    final_result: FinalResultState = field(default_factory=FinalResultState)

    @classmethod
    def initial(cls, random_seed: int = 0) -> GameState:
        return cls(random=RandomState.initial(random_seed))
