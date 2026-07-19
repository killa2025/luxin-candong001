from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from math import floor
from typing import Any

from furnace_winter.config import BuildingRule, BuildingRules, SurvivalRules
from furnace_winter.gameplay.end_day import EndDayContext, EndDayEngine, EndDayStage
from furnace_winter.gameplay.survival import is_over_capacity, storage_used
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
from furnace_winter.models import BuildingState, GameState, SaveDataError, validate_game_state


BUILD_COMMAND = "game.build"
UPGRADE_COMMAND = "game.upgrade"
ASSIGN_COMMAND = "game.assign"
UNASSIGN_COMMAND = "game.unassign"
HEAT_COMMAND = "game.heat"
WOODFUEL_COMMAND = "game.woodfuel"

_STAFF_FIELDS = {
    "workers": "assigned_workers",
    "engineers": "assigned_engineers",
    "children": "assigned_children",
    "medical_apprentices": "assigned_medical_apprentices",
    "engineering_apprentices": "assigned_engineering_apprentices",
}
_POPULATION_FIELDS = {
    "workers": "workers",
    "engineers": "engineers",
    "children": "children",
    "medical_apprentices": "medical_apprentices",
    "engineering_apprentices": "engineering_apprentices",
}


def build_building_catalog(rules: BuildingRules | None = None) -> CommandCatalog:
    catalog = CommandCatalog()
    buildable_types = (
        tuple(sorted(key for key, rule in rules.buildings.items() if rule.buildable))
        if rules is not None
        else ()
    )
    upgrade_ids = tuple(sorted(rules.upgrades)) if rules is not None else ()
    catalog.register(
        CommandSpec(
            name=BUILD_COMMAND,
            required_arguments={
                "building_type": ArgumentKind.STRING,
                "zone": ArgumentKind.STRING,
            },
            optional_arguments={"binding_id": ArgumentKind.STRING},
            argument_options={
                **({"building_type": buildable_types} if buildable_types else {}),
                "zone": ("inner_ring", "middle_ring", "outer_ring", "storage_outer"),
            },
        )
    )
    catalog.register(
        CommandSpec(
            name=UPGRADE_COMMAND,
            required_arguments={
                "building_id": ArgumentKind.STRING,
                "upgrade_id": ArgumentKind.STRING,
            },
            argument_options={"upgrade_id": upgrade_ids} if upgrade_ids else {},
        )
    )
    catalog.register(
        CommandSpec(
            name=ASSIGN_COMMAND,
            required_arguments={
                "building_id": ArgumentKind.STRING,
                "population_type": ArgumentKind.STRING,
                "count": ArgumentKind.INTEGER,
            },
            argument_options={"population_type": tuple(_STAFF_FIELDS)},
        )
    )
    catalog.register(
        CommandSpec(
            name=UNASSIGN_COMMAND,
            required_arguments={
                "building_id": ArgumentKind.STRING,
                "population_type": ArgumentKind.STRING,
            },
            optional_arguments={"count": ArgumentKind.INTEGER},
            argument_options={"population_type": tuple(_STAFF_FIELDS)},
        )
    )
    catalog.register(
        CommandSpec(
            name=HEAT_COMMAND,
            required_arguments={"building_id": ArgumentKind.STRING},
        )
    )
    catalog.register(
        CommandSpec(
            name=WOODFUEL_COMMAND,
            required_arguments={"confirm": ArgumentKind.BOOLEAN},
        )
    )
    return catalog


class BuildingSystem:
    """Patch 004 manual building actions and deterministic daily operation."""

    def __init__(self, rules: BuildingRules, survival_rules: SurvivalRules) -> None:
        self.rules = rules
        self.survival_rules = survival_rules
        self._catalog = build_building_catalog(rules)
        self._validator = CommandValidator(self._catalog)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def execute(self, state: GameState, request: CommandRequest) -> CommandResult:
        command_id = request.command_id if isinstance(request, CommandRequest) and isinstance(request.command_id, str) else ""
        state_sequence = state.command_sequence if isinstance(state, GameState) and isinstance(state.command_sequence, int) else 0
        validation = self._validator.validate(request)
        if not validation.is_valid:
            return self._rejected(command_id, state_sequence, validation)
        try:
            validate_game_state(state)
        except (SaveDataError, TypeError, ValueError) as exc:
            return self._error(command_id, state_sequence, "input_state_validation", exc)
        validation = self._validator.validate(request, state, self._legality)
        if not validation.is_valid:
            return self._rejected(command_id, state_sequence, validation)

        working = deepcopy(state)
        data: dict[str, Any]
        try:
            if request.name == BUILD_COMMAND:
                data = self._build(working, request)
            elif request.name == UPGRADE_COMMAND:
                data = self._upgrade(working, request)
            elif request.name in {ASSIGN_COMMAND, UNASSIGN_COMMAND}:
                data = self._assign(working, request)
            elif request.name == HEAT_COMMAND:
                data = self._heat(working, request)
            elif request.name == WOODFUEL_COMMAND:
                data = self._woodfuel(working)
            else:
                return self._rejected(
                    command_id,
                    state_sequence,
                    CommandValidation(False, ErrorCode.ILLEGAL_COMMAND),
                )
            working.command_sequence += 1
            validate_game_state(working)
        except (SaveDataError, TypeError, ValueError) as exc:
            return self._error(command_id, state_sequence, "result_state_validation", exc)

        for item in fields(GameState):
            setattr(state, item.name, deepcopy(getattr(working, item.name)))
        return CommandResult(
            command_id=command_id,
            accepted=True,
            code=ErrorCode.OK,
            state_changed=True,
            state_sequence=state.command_sequence,
            feedback=(FeedbackItem(FeedbackLevel.INFO, data=data),),
            data=data,
        )

    def _legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        blocked = self._planning_block(state)
        if blocked is not None:
            return blocked
        if request.name == BUILD_COMMAND:
            return self._build_legality(state, request)
        if request.name == UPGRADE_COMMAND:
            return self._upgrade_legality(state, request)
        if request.name in {ASSIGN_COMMAND, UNASSIGN_COMMAND}:
            return self._assign_legality(state, request)
        if request.name == HEAT_COMMAND:
            return self._heat_legality(state, request)
        if request.name == WOODFUEL_COMMAND:
            return self._woodfuel_legality(state, request)
        return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND)

    @staticmethod
    def _planning_block(state: GameState) -> CommandValidation | None:
        if state.final_result.hard_fail_type is not None:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "game_already_failed"})
        if state.calendar.is_day_locked or state.final_result.is_finalized:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "day_not_open_for_planning"})
        return None

    def _build_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_type = request.arguments.get("building_type")
        zone = request.arguments.get("zone")
        rule = self.rules.buildings.get(building_type) if isinstance(building_type, str) else None
        if rule is None:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building_type"})
        if not rule.buildable:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_is_upgrade_only"})
        if zone not in rule.allowed_zones:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "zone_not_allowed", "allowed_zones": list(rule.allowed_zones)})
        signed_laws = set(state.laws.signed_law_ids) | set(state.laws.active_law_ids)
        missing_laws = sorted(set(rule.required_law_ids) - signed_laws)
        missing_techs = sorted(set(rule.required_tech_ids) - set(state.technologies.researched_tech_ids))
        if missing_laws or missing_techs:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "prerequisite_missing", "missing_law_ids": missing_laws, "missing_tech_ids": missing_techs})
        if state.resources.wood < rule.wood_cost or state.resources.steel < rule.steel_cost:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_resources", "required_wood": rule.wood_cost, "required_steel": rule.steel_cost})
        assert isinstance(zone, str)
        used = state.building_management.zone_slots_used[zone]
        capacity = state.building_management.zone_slot_capacity[zone]
        if used + rule.slot_size > capacity:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_zone_slots", "used": used, "capacity": capacity})
        maximum = self._building_limit(state, rule)
        current = sum(1 for item in state.buildings.values() if item.building_type == rule.building_type)
        if maximum is not None and current >= maximum:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_limit_reached", "limit": maximum})
        if building_type == "cemetery" and self._has_type(state, "cold_pit") or building_type == "cold_pit" and self._has_type(state, "cemetery"):
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "mutually_exclusive_building_exists"})
        binding_id = request.arguments.get("binding_id")
        if rule.binding_kind is None:
            if binding_id is not None:
                return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "binding_not_supported"})
        else:
            valid_ids = self.rules.resource_anchors[rule.binding_kind]
            if binding_id not in valid_ids:
                return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "invalid_resource_binding", "binding_kind": rule.binding_kind})
            if any(item.bound_resource_id == binding_id for item in state.buildings.values()):
                return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "resource_anchor_already_bound"})
        return CommandValidation.valid()

    def _upgrade_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_id = request.arguments.get("building_id")
        upgrade_id = request.arguments.get("upgrade_id")
        building = state.buildings.get(building_id) if isinstance(building_id, str) else None
        upgrade = self.rules.upgrades.get(upgrade_id) if isinstance(upgrade_id, str) else None
        if building is None or upgrade is None:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building_or_upgrade"})
        if building.building_type != upgrade.from_type:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "upgrade_not_supported_for_building"})
        if upgrade.required_tech_id not in state.technologies.researched_tech_ids:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "prerequisite_missing", "missing_tech_ids": [upgrade.required_tech_id]})
        if state.resources.wood < upgrade.wood_cost or state.resources.steel < upgrade.steel_cost:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_resources", "required_wood": upgrade.wood_cost, "required_steel": upgrade.steel_cost})
        return CommandValidation.valid()

    def _assign_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_id = request.arguments.get("building_id")
        population_type = request.arguments.get("population_type")
        building = state.buildings.get(building_id) if isinstance(building_id, str) else None
        if building is None or population_type not in _STAFF_FIELDS:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building_or_population_type"})
        rule = self.rules.buildings.get(building.building_type)
        if rule is None:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_type_not_in_catalog"})
        current = getattr(building, _STAFF_FIELDS[population_type])
        if request.name == UNASSIGN_COMMAND:
            remove_count = request.arguments.get("count")
            if remove_count is not None and (
                not isinstance(remove_count, int)
                or isinstance(remove_count, bool)
                or remove_count < 0
                or remove_count > current
            ):
                return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "invalid_unassign_count", "assigned_count": current})
            target = 0 if remove_count is None else current - remove_count
        else:
            target = request.arguments.get("count")
        if not isinstance(target, int) or isinstance(target, bool) or target < 0:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "count_must_be_nonnegative"})
        if population_type not in rule.allowed_staff_types and target > 0:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "population_type_not_allowed"})
        field_name = _STAFF_FIELDS[population_type]
        assigned_total = self._assigned_total(building) - current + target
        if assigned_total > rule.staff_capacity:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "staff_capacity_exceeded", "capacity": rule.staff_capacity})
        population_available = getattr(state.population, _POPULATION_FIELDS[population_type])
        assigned_elsewhere = sum(getattr(item, field_name) for item in state.buildings.values() if item.building_id != building.building_id)
        if assigned_elsewhere + target > population_available:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "population_not_available", "available": population_available - assigned_elsewhere})
        return CommandValidation.valid()

    def _heat_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        building_id = request.arguments.get("building_id")
        building = state.buildings.get(building_id) if isinstance(building_id, str) else None
        if building is None:
            return CommandValidation(False, ErrorCode.INVALID_ARGUMENTS, {"reason": "unknown_building"})
        if not building.can_heat:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_cannot_heat"})
        if building.heated_today:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "building_already_heated_today"})
        if state.resources.coal < self.rules.heat.coal_cost:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_coal", "required_coal": self.rules.heat.coal_cost})
        return CommandValidation.valid()

    def _woodfuel_legality(self, state: GameState, request: CommandRequest) -> CommandValidation:
        if request.arguments.get("confirm") is not True:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "confirmation_required"})
        if not state.furnace.is_active:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "furnace_is_off"})
        if state.building_management.woodfuel_confirmed_today:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "woodfuel_already_confirmed_today"})
        level = int(state.furnace.mode_id[-1])
        required_coal = self.survival_rules.furnace_levels[level].coal_cost
        if state.resources.coal >= required_coal:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "no_base_heating_shortfall"})
        if state.resources.wood < self.rules.woodfuel.minimum_wood_unit:
            return CommandValidation(False, ErrorCode.ILLEGAL_COMMAND, {"reason": "insufficient_wood", "minimum_wood": self.rules.woodfuel.minimum_wood_unit})
        return CommandValidation.valid()

    def _build(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building_type = str(request.arguments["building_type"])
        zone = str(request.arguments["zone"])
        rule = self.rules.buildings[building_type]
        sequence = state.building_management.next_building_sequence
        while True:
            building_id = f"building-{sequence:06d}"
            sequence += 1
            if building_id not in state.buildings:
                break
        state.building_management.next_building_sequence = sequence
        state.resources.wood -= rule.wood_cost
        state.resources.steel -= rule.steel_cost
        state.buildings[building_id] = BuildingState(
            building_id=building_id,
            building_type=building_type,
            zone=zone,
            slot_size=rule.slot_size,
            is_built=True,
            is_operational=rule.staff_capacity == 0,
            can_heat=rule.can_heat,
            bound_resource_id=request.arguments.get("binding_id"),
        )
        state.building_management.zone_slots_used[zone] += rule.slot_size
        state.housing.capacity += rule.housing_capacity
        if building_type == "basic_residence":
            state.housing.basic_residences += 1
        state.resources.storage_capacity += rule.storage_capacity_add
        self._sync_housing_population(state)
        second_hunting_area_unlocked = False
        if building_type == "hunting_lodge" and state.building_management.available_hunting_areas == 1:
            state.building_management.available_hunting_areas = 2
            second_hunting_area_unlocked = True
        return {
            "building_id": building_id,
            "building_type": building_type,
            "zone": zone,
            "wood_paid": rule.wood_cost,
            "steel_paid": rule.steel_cost,
            "second_hunting_area_unlocked": second_hunting_area_unlocked,
        }

    def _upgrade(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building = state.buildings[str(request.arguments["building_id"])]
        upgrade = self.rules.upgrades[str(request.arguments["upgrade_id"])]
        old_rule = self.rules.buildings[upgrade.from_type]
        new_rule = self.rules.buildings[upgrade.to_type]
        state.resources.wood -= upgrade.wood_cost
        state.resources.steel -= upgrade.steel_cost
        building.building_type = upgrade.to_type
        building.slot_size = new_rule.slot_size
        building.can_heat = new_rule.can_heat
        state.housing.capacity += new_rule.housing_capacity - old_rule.housing_capacity
        if upgrade.from_type == "basic_residence":
            state.housing.basic_residences -= 1
        state.resources.storage_capacity += new_rule.storage_capacity_add - old_rule.storage_capacity_add
        self._sync_housing_population(state)
        return {
            "building_id": building.building_id,
            "upgrade_id": upgrade.upgrade_id,
            "building_type": upgrade.to_type,
            "wood_paid": upgrade.wood_cost,
            "steel_paid": upgrade.steel_cost,
            "instant": True,
        }

    def _assign(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building = state.buildings[str(request.arguments["building_id"])]
        population_type = str(request.arguments["population_type"])
        if request.name == UNASSIGN_COMMAND:
            current = getattr(building, _STAFF_FIELDS[population_type])
            remove_count = request.arguments.get("count")
            target = 0 if remove_count is None else current - int(remove_count)
        else:
            target = int(request.arguments["count"])
        setattr(building, _STAFF_FIELDS[population_type], target)
        rule = self.rules.buildings[building.building_type]
        building.is_operational = rule.staff_capacity == 0 or self._assigned_total(building) > 0
        return {"building_id": building.building_id, "population_type": population_type, "assigned_count": target}

    def _heat(self, state: GameState, request: CommandRequest) -> dict[str, Any]:
        building = state.buildings[str(request.arguments["building_id"])]
        state.resources.coal -= self.rules.heat.coal_cost
        building.heated_today = True
        bonus = self._heat_bonus(state)
        return {"building_id": building.building_id, "coal_paid": self.rules.heat.coal_cost, "temperature_bonus": bonus}

    @staticmethod
    def _woodfuel(state: GameState) -> dict[str, Any]:
        state.building_management.woodfuel_confirmed_today = True
        return {"woodfuel_confirmed_today": True, "active_duration": "current_day_only"}

    def install(self, engine: EndDayEngine) -> None:
        engine.register_stage_handler(EndDayStage.CALCULATE_BUILDING_TEMPERATURE, self.calculate_building_temperatures)
        engine.register_stage_handler(EndDayStage.RESOLVE_BUILDING_OPERATION, self.resolve_building_operation)
        engine.register_stage_handler(EndDayStage.RESOLVE_COLLECTION_AND_PRODUCTION, self.resolve_production)
        engine.register_stage_handler(EndDayStage.CLOSE_DAILY_EFFECTS, self.close_daily_effects)

    def calculate_building_temperatures(self, context: EndDayContext) -> None:
        state = context.state
        zones = state.daily_survival.zone_temperatures
        if not zones:
            context.abort(ErrorCode.INTERNAL_ERROR, {"reason": "zone_temperature_not_calculated"})
        base_insulation = 12 if "tech_building_insulation_2" in state.technologies.researched_tech_ids else 6 if "tech_building_insulation_1" in state.technologies.researched_tech_ids else 0
        for building in state.buildings.values():
            rule = self.rules.buildings.get(building.building_type)
            if rule is None:
                continue
            zone_temperature = zones["outer_ring"] if building.zone == "storage_outer" else zones[building.zone]
            bonus = 0
            if building.building_type in {"basic_residence", "improved_residence", "advanced_residence"}:
                if "tech_housing_insulation_1" in state.technologies.researched_tech_ids:
                    bonus += 4
            elif building.building_type not in {"small_warehouse", "cemetery", "cold_pit", "gathering_shelter"}:
                bonus += base_insulation
            if building.building_type in {"medical_station", "hospital"} and "tech_medical_building_insulation" in state.technologies.researched_tech_ids:
                bonus += 8
            if building.heated_today:
                bonus += self._heat_bonus(state)
            building.effective_temperature = zone_temperature + bonus
        context.emit("buildings.temperature.calculated", {"building_count": len(state.buildings)})

    def resolve_building_operation(self, context: EndDayContext) -> None:
        for building in context.state.buildings.values():
            rule = self.rules.buildings.get(building.building_type)
            if rule is None:
                building.is_operational = False
                continue
            building.is_shutdown_by_temperature = (
                rule.min_operating_temperature is not None
                and building.effective_temperature < rule.min_operating_temperature
            )
            staffed = rule.staff_capacity == 0 or self._assigned_total(building) > 0
            building.is_operational = building.is_built and staffed and not building.is_shutdown_by_temperature
        context.emit(
            "buildings.operation.resolved",
            {"operational_count": sum(item.is_operational for item in context.state.buildings.values())},
        )

    def resolve_production(self, context: EndDayContext) -> None:
        state = context.state
        production: dict[str, int] = {"coal": 0, "wood": 0, "steel": 0, "raw_food": 0}
        canteens: list[tuple[BuildingState, BuildingRule]] = []
        for building in state.buildings.values():
            rule = self.rules.buildings.get(building.building_type)
            if rule is None or not building.is_operational:
                continue
            if rule.raw_food_processing_cap:
                canteens.append((building, rule))
                continue
            if rule.output_resource is None or rule.output_per_day == 0:
                continue
            output = floor(rule.output_per_day * self._assigned_total(building) / rule.staff_capacity) if rule.staff_capacity else rule.output_per_day
            if building.building_type == "logging_camp" and "tech_wood_processing_2" in state.technologies.researched_tech_ids:
                output = floor(70 * self._assigned_total(building) / rule.staff_capacity)
            elif building.building_type == "small_coal_miner" and "tech_small_coal_mining_improvement" in state.technologies.researched_tech_ids:
                output = floor(90 * self._assigned_total(building) / rule.staff_capacity)
            elif building.building_type == "small_steel_miner" and "tech_small_steel_mining_improvement" in state.technologies.researched_tech_ids:
                output = floor(30 * self._assigned_total(building) / rule.staff_capacity)
            setattr(state.resources, rule.output_resource, getattr(state.resources, rule.output_resource) + output)
            production[rule.output_resource] += output

        raw_processed = 0
        cooked_produced = 0
        for building, rule in canteens:
            cap = 80 if "tech_canteen_process_improvement" in state.technologies.researched_tech_ids else rule.raw_food_processing_cap
            staffed_cap = floor(cap * self._assigned_total(building) / rule.staff_capacity)
            processed = min(staffed_cap, state.resources.raw_food)
            state.resources.raw_food -= processed
            cooked = processed * self.survival_rules.raw_to_cooked_ratio
            state.resources.cooked_food += cooked
            raw_processed += processed
            cooked_produced += cooked
        state.daily_survival.storage_used = storage_used(state.resources)
        state.daily_survival.is_over_capacity = is_over_capacity(state.resources)
        context.emit("buildings.production.settled", {"production": production, "raw_food_processed": raw_processed, "cooked_food_produced": cooked_produced})

    @staticmethod
    def close_daily_effects(context: EndDayContext) -> None:
        for building in context.state.buildings.values():
            building.heated_today = False
        context.state.building_management.woodfuel_confirmed_today = False
        context.emit("buildings.daily_effects.closed", {"heat_reset": True, "woodfuel_reset": True})

    def _building_limit(self, state: GameState, rule: BuildingRule) -> int | None:
        if rule.max_count_source == "hunting_areas":
            return state.building_management.available_hunting_areas
        if rule.max_count_source == "forest_zones":
            return state.building_management.forest_zones
        return rule.max_buildings

    def _heat_bonus(self, state: GameState) -> int:
        return self.rules.heat.enhanced_temperature_bonus if self.rules.heat.enhancement_tech_id in state.technologies.researched_tech_ids else self.rules.heat.temperature_bonus

    @staticmethod
    def _has_type(state: GameState, building_type: str) -> bool:
        return any(item.building_type == building_type for item in state.buildings.values())

    @staticmethod
    def _assigned_total(building: BuildingState) -> int:
        return sum(getattr(building, field_name) for field_name in _STAFF_FIELDS.values())

    @staticmethod
    def _sync_housing_population(state: GameState) -> None:
        housed = min(state.population.population_alive, state.housing.capacity)
        state.population.housed_population = housed
        state.population.homeless_population = state.population.population_alive - housed

    @staticmethod
    def _rejected(command_id: str, sequence: int, validation: CommandValidation) -> CommandResult:
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=validation.code,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=validation.details),),
            data=validation.details,
        )

    @staticmethod
    def _error(command_id: str, sequence: int, stage: str, exc: Exception) -> CommandResult:
        details = {"failed_stage": stage, "exception_type": type(exc).__name__}
        return CommandResult(
            command_id=command_id,
            accepted=False,
            code=ErrorCode.INTERNAL_ERROR,
            state_sequence=sequence,
            feedback=(FeedbackItem(FeedbackLevel.ERROR, data=details),),
            data=details,
        )
