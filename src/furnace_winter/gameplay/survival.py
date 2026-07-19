from __future__ import annotations

from copy import deepcopy
from dataclasses import fields

from furnace_winter.config import BuildingRules, SurvivalRules
from furnace_winter.gameplay.end_day import (
    EndDayContext,
    EndDayEngine,
    EndDayStage,
    RiskWarning,
    RiskWarningLevel,
)
from furnace_winter.interface import (
    ArgumentKind,
    CommandCatalog,
    CommandRequest,
    CommandResult,
    CommandSpec,
    CommandValidation,
    CommandValidator,
    ErrorCode,
    FeedbackItem,
    FeedbackLevel,
)
from furnace_winter.models import (
    BuildingState,
    DailySurvivalState,
    GameState,
    HousingState,
    PopulationState,
    ResourceState,
    SaveDataError,
    TrustPanicState,
    validate_game_state,
)


SET_FURNACE_COMMAND = "game.set_furnace"
FURNACE_LEVEL_ARGUMENT = "level"


def furnace_mode_id(level: int) -> str:
    if level not in {0, 1, 2, 3}:
        raise ValueError("furnace level must be between 0 and 3")
    return "off" if level == 0 else f"level_{level}"


def furnace_level(mode_id: str) -> int:
    if mode_id == "off":
        return 0
    if mode_id in {"level_1", "level_2", "level_3"}:
        return int(mode_id[-1])
    raise ValueError(f"unsupported furnace mode: {mode_id!r}")


def storage_used(resources: ResourceState) -> int:
    return (
        resources.coal
        + resources.wood
        + resources.steel
        + resources.raw_food
        + resources.cooked_food
    )


def is_over_capacity(resources: ResourceState) -> bool:
    return storage_used(resources) > resources.storage_capacity


def create_initial_survival_state(
    rules: SurvivalRules,
    *,
    random_seed: int = 0,
) -> GameState:
    state = GameState.initial(random_seed=random_seed)
    total = rules.population.total
    housing_capacity = rules.starting_housing_capacity
    state.population = PopulationState(
        population_total=total,
        population_alive=total,
        population_dead=0,
        workers=rules.population.workers,
        engineers=rules.population.engineers,
        children=rules.population.children,
        healthy_population=total,
        sick_population=0,
        critical_population=0,
        disabled_population=0,
        housed_population=min(total, housing_capacity),
        homeless_population=max(total - housing_capacity, 0),
    )
    state.resources = ResourceState(
        coal=rules.resources.coal,
        wood=rules.resources.wood,
        steel=rules.resources.steel,
        raw_food=rules.resources.raw_food,
        cooked_food=rules.resources.cooked_food,
        storage_capacity=rules.resources.storage_capacity,
    )
    state.housing = HousingState(
        basic_residences=rules.basic_residences,
        capacity=housing_capacity,
    )
    for index in range(1, rules.basic_residences + 1):
        building_id = f"residence-start-{index:03d}"
        state.buildings[building_id] = BuildingState(
            building_id=building_id,
            building_type="basic_residence",
            zone="inner_ring",
            slot_size=1,
            is_built=True,
            is_operational=True,
            can_heat=False,
        )
    state.building_management.zone_slots_used["inner_ring"] = rules.basic_residences
    state.furnace.is_active = rules.starting_furnace_level > 0
    state.furnace.mode_id = furnace_mode_id(rules.starting_furnace_level)
    state.trust_panic = TrustPanicState(
        trust=rules.starting_trust,
        panic=rules.starting_panic,
    )
    state.daily_survival.storage_used = storage_used(state.resources)
    state.daily_survival.is_over_capacity = is_over_capacity(state.resources)
    validate_game_state(state)
    return state


def build_survival_catalog() -> CommandCatalog:
    catalog = CommandCatalog()
    catalog.register(
        CommandSpec(
            name=SET_FURNACE_COMMAND,
            required_arguments={FURNACE_LEVEL_ARGUMENT: ArgumentKind.INTEGER},
        )
    )
    return catalog


class SurvivalSystem:
    """Patch 003 population, resource, food, housing, and furnace foundation."""

    def __init__(
        self,
        rules: SurvivalRules,
        building_rules: BuildingRules | None = None,
    ) -> None:
        self.rules = rules
        self.building_rules = building_rules
        self._catalog = build_survival_catalog()
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        request_validation = self._validator.validate(request)
        command_id = (
            request.command_id
            if isinstance(request, CommandRequest)
            and isinstance(request.command_id, str)
            else ""
        )
        state_sequence = (
            state.command_sequence
            if isinstance(state, GameState)
            and isinstance(state.command_sequence, int)
            and not isinstance(state.command_sequence, bool)
            else 0
        )
        if not request_validation.is_valid:
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=request_validation.code,
                state_sequence=state_sequence,
                feedback=(
                    FeedbackItem(FeedbackLevel.ERROR, data=request_validation.details),
                ),
                data=request_validation.details,
            )

        try:
            validate_game_state(state)
        except (SaveDataError, TypeError, ValueError) as exc:
            details = {
                "failed_stage": "input_state_validation",
                "exception_type": type(exc).__name__,
            }
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INTERNAL_ERROR,
                state_sequence=state_sequence,
                feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
                data=details,
            )

        validation = self._validator.validate(
            request,
            state,
            self._furnace_legality,
        )
        if not validation.is_valid:
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=validation.code,
                state_sequence=state_sequence,
                feedback=(FeedbackItem(FeedbackLevel.ERROR, data=validation.details),),
                data=validation.details,
            )

        level = request.arguments[FURNACE_LEVEL_ARGUMENT]
        assert isinstance(level, int) and not isinstance(level, bool)
        working = deepcopy(state)
        working.furnace.is_active = level > 0
        working.furnace.mode_id = furnace_mode_id(level)
        working.command_sequence += 1
        try:
            validate_game_state(working)
        except (SaveDataError, TypeError, ValueError) as exc:
            details = {
                "failed_stage": "result_state_validation",
                "exception_type": type(exc).__name__,
            }
            return CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INTERNAL_ERROR,
                state_sequence=state_sequence,
                feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
                data=details,
            )
        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        return CommandResult(
            command_id=request.command_id,
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data={"furnace_level": level}),),
            data={"furnace_level": level},
        )

    @staticmethod
    def _furnace_legality(
        state: GameState,
        request: CommandRequest,
    ) -> CommandValidation:
        if request.name != SET_FURNACE_COMMAND:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND)
        if state.final_result.hard_fail_type is not None:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "game_already_failed"},
            )
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            return CommandValidation(
                False,
                ErrorCode.ILLEGAL_COMMAND,
                {"reason": "day_not_open_for_planning"},
            )
        level = request.arguments.get(FURNACE_LEVEL_ARGUMENT)
        if level not in {0, 1, 2, 3}:
            return CommandValidation(
                False,
                ErrorCode.INVALID_ARGUMENTS,
                {"invalid_furnace_level": level},
            )
        return CommandValidation.valid()

    def install(self, engine: EndDayEngine) -> None:
        engine.register_risk_evaluator(self.evaluate_risks)
        engine.register_stage_handler(
            EndDayStage.PAY_HEATING_AND_OVERLOAD,
            self.settle_heating,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_ACTUAL_HEATING,
            self.resolve_actual_heating,
        )
        engine.register_stage_handler(
            EndDayStage.CALCULATE_ZONE_TEMPERATURE,
            self.calculate_zone_temperatures,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_FOOD_CHAIN,
            self.settle_food,
        )
        engine.register_stage_handler(
            EndDayStage.RESOLVE_HOUSING_COLD_AND_HUNGER,
            self.settle_housing,
        )

    def evaluate_risks(self, state: GameState) -> tuple[RiskWarning, ...]:
        warnings: list[RiskWarning] = []
        target_level = furnace_level(state.furnace.mode_id)
        required_coal = self.rules.furnace_levels[target_level].coal_cost
        affordable_level = self._affordable_level(target_level, state)
        if target_level == 0:
            warnings.append(
                RiskWarning(
                    "survival.furnace_off",
                    RiskWarningLevel.B_STRONG,
                    {"target_level": 0},
                )
            )
        elif affordable_level < target_level:
            warnings.append(
                RiskWarning(
                    "survival.heating_fuel_shortfall",
                    RiskWarningLevel.B_STRONG,
                    {
                        "available_coal": state.resources.coal,
                        "required_coal": required_coal,
                        "target_level": target_level,
                        "affordable_level": affordable_level,
                    },
                )
            )

        food_required = state.population.population_alive * self.rules.food_per_person
        available_food = state.resources.cooked_food + state.resources.raw_food
        if available_food < food_required:
            warnings.append(
                RiskWarning(
                    "survival.food_shortfall",
                    RiskWarningLevel.B_STRONG,
                    {
                        "available_food": available_food,
                        "required_food": food_required,
                        "unfed_population": food_required - available_food,
                    },
                )
            )
        if state.population.homeless_population > 0:
            warnings.append(
                RiskWarning(
                    "survival.housing_shortfall",
                    RiskWarningLevel.A_INFO,
                    {"homeless_population": state.population.homeless_population},
                )
            )
        if is_over_capacity(state.resources):
            warnings.append(
                RiskWarning(
                    "survival.storage_over_capacity",
                    RiskWarningLevel.A_INFO,
                    {
                        "capacity": state.resources.storage_capacity,
                        "used": storage_used(state.resources),
                    },
                )
            )
        return tuple(warnings)

    def _affordable_level(self, target_level: int, state: GameState) -> int:
        available_fuel = state.resources.coal + self._woodfuel_available(state)
        return max(
            level
            for level in range(target_level + 1)
            if self.rules.furnace_levels[level].coal_cost <= available_fuel
        )

    def _woodfuel_available(self, state: GameState) -> int:
        if (
            self.building_rules is None
            or not state.building_management.woodfuel_confirmed_today
        ):
            return 0
        rule = self.building_rules.woodfuel
        usable_wood = min(state.resources.wood, rule.daily_wood_limit)
        usable_wood -= usable_wood % rule.minimum_wood_unit
        return usable_wood // rule.wood_per_fuel

    def settle_heating(self, context: EndDayContext) -> None:
        state = context.state
        target_level = furnace_level(state.furnace.mode_id)
        target_rule = self.rules.furnace_levels[target_level]
        effective_level = self._affordable_level(target_level, state)
        effective_rule = self.rules.furnace_levels[effective_level]
        coal_paid = min(state.resources.coal, effective_rule.coal_cost)
        contribution = effective_rule.coal_cost - coal_paid
        wood_burned = 0
        if contribution:
            if self.building_rules is None:
                context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "woodfuel_rules_missing"})
            wood_burned = contribution * self.building_rules.woodfuel.wood_per_fuel
            state.resources.wood -= wood_burned
        state.resources.coal -= coal_paid
        state.daily_survival = DailySurvivalState(
            settled_day=context.settled_day,
            base_temperature=self.rules.weather_for_day(context.settled_day),
            target_furnace_level=target_level,
            effective_furnace_level=effective_level,
            required_coal=target_rule.coal_cost,
            coal_paid=coal_paid,
            woodfuel_wood_burned=wood_burned,
            woodfuel_contribution=contribution,
            heating_shortfall=effective_level < target_level,
            storage_used=storage_used(state.resources),
            is_over_capacity=is_over_capacity(state.resources),
        )
        context.emit(
            "survival.heating.settled",
            {
                "target_level": target_level,
                "effective_level": effective_level,
                "required_coal": target_rule.coal_cost,
                "coal_paid": coal_paid,
                "woodfuel_wood_burned": wood_burned,
                "woodfuel_contribution": contribution,
                "heating_shortfall": effective_level < target_level,
            },
        )

    @staticmethod
    def resolve_actual_heating(context: EndDayContext) -> None:
        summary = context.state.daily_survival
        if summary.settled_day != context.settled_day:
            context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "heating_not_settled"})
        effective_level = summary.effective_furnace_level
        context.state.furnace.mode_id = furnace_mode_id(effective_level)
        context.state.furnace.is_active = effective_level > 0
        context.emit(
            "survival.heating.actual_level_resolved",
            {"effective_level": effective_level},
        )

    def calculate_zone_temperatures(self, context: EndDayContext) -> None:
        summary = context.state.daily_survival
        if summary.base_temperature is None:
            context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "heating_not_settled"})
        heating = self.rules.furnace_levels[summary.effective_furnace_level].heating
        summary.zone_temperatures = {
            zone: summary.base_temperature + heating + modifier
            for zone, modifier in self.rules.zone_modifiers.items()
        }
        context.emit(
            "survival.temperature.calculated",
            {
                "base_temperature": summary.base_temperature,
                "furnace_heating": heating,
                "zones": summary.zone_temperatures,
            },
        )

    def settle_food(self, context: EndDayContext) -> None:
        state = context.state
        required = state.population.population_alive * self.rules.food_per_person
        cooked_eaten = min(required, state.resources.cooked_food)
        state.resources.cooked_food -= cooked_eaten
        remaining = required - cooked_eaten
        raw_eaten = min(remaining, state.resources.raw_food)
        state.resources.raw_food -= raw_eaten
        unfed = remaining - raw_eaten
        state.daily_survival.cooked_food_eaten = cooked_eaten
        state.daily_survival.raw_food_eaten = raw_eaten
        state.daily_survival.unfed_population = unfed
        state.daily_survival.storage_used = storage_used(state.resources)
        state.daily_survival.is_over_capacity = is_over_capacity(state.resources)
        context.emit(
            "survival.food.settled",
            {
                "required_food": required,
                "cooked_food_eaten": cooked_eaten,
                "raw_food_eaten": raw_eaten,
                "unfed_population": unfed,
            },
        )

    @staticmethod
    def settle_housing(context: EndDayContext) -> None:
        state = context.state
        alive = state.population.population_alive
        housed = min(alive, state.housing.capacity)
        state.population.housed_population = housed
        state.population.homeless_population = alive - housed
        context.emit(
            "survival.housing.settled",
            {
                "housing_capacity": state.housing.capacity,
                "housed_population": housed,
                "homeless_population": alive - housed,
            },
        )
