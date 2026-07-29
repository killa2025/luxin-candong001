from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from furnace_winter.config import (
    load_building_rules,
    load_event_rules,
    load_final_frost_rules,
    load_law_rules,
    load_oath_order_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    BuildingSystem,
    EndDayEngine,
    EndDayExecution,
    EndingReportSystem,
    EventSystem,
    FinalFrostSystem,
    LawSystem,
    OathOrderSystem,
    RiskWarning,
    SurvivalSystem,
    TechnologySystem,
    create_initial_survival_state,
    storage_used,
)
from furnace_winter.interface.commands import (
    CommandCatalog,
    CommandRequest,
    CommandSpec,
    CommandValidation,
    CommandValidator,
    ErrorCode,
)
from furnace_winter.interface.feedback import CommandResult
from furnace_winter.interface.observation import Observation, PROTOCOL_VERSION
from furnace_winter.interface.replay import (
    LogCategory,
    LogEntry,
    ReplayDocument,
    ReplayEntry,
    ReplayLog,
)
from furnace_winter.models import (
    GameState,
    RandomState,
    decode_game_state,
    dumps,
    encode_game_state,
    validate_game_state,
)


_CONFIG_FILENAMES = {
    "survival": "survival.json",
    "buildings": "buildings.json",
    "laws": "laws.json",
    "technologies": "technologies.json",
    "events": "events.json",
    "oath_order": "oath_order.json",
    "final_frost": "final_frost.json",
}


@dataclass(frozen=True, slots=True)
class SessionExecution:
    """One command result plus a compact, non-strategic state summary."""

    protocol_version: int
    replay_sequence: int | None
    result: CommandResult
    status: Mapping[str, Any]
    warnings: tuple[RiskWarning, ...] = ()
    save_written: bool = False


class GameSession:
    """Wire every implemented gameplay system into one persistent AI entrypoint."""

    def __init__(
        self,
        *,
        config_dir: Path,
        state: GameState,
        save_path: Path | None,
        rule_documents: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self.config_dir = config_dir
        self.save_path = save_path
        self._state = state
        self._rule_documents = {
            key: deepcopy(dict(document))
            for key, document in rule_documents.items()
        }
        self._attempt_sequence = 0
        self._last_end_day_autosave = None

        self.survival_rules = load_survival_rules(
            config_dir / _CONFIG_FILENAMES["survival"]
        )
        self.building_rules = load_building_rules(
            config_dir / _CONFIG_FILENAMES["buildings"]
        )
        self.law_rules = load_law_rules(
            config_dir / _CONFIG_FILENAMES["laws"]
        )
        self.technology_rules = load_technology_rules(
            config_dir / _CONFIG_FILENAMES["technologies"]
        )
        self.event_rules = load_event_rules(
            config_dir / _CONFIG_FILENAMES["events"]
        )
        self.oath_order_rules = load_oath_order_rules(
            config_dir / _CONFIG_FILENAMES["oath_order"]
        )
        self.final_frost_rules = load_final_frost_rules(
            config_dir / _CONFIG_FILENAMES["final_frost"]
        )

        self.survival = SurvivalSystem(
            self.survival_rules,
            self.building_rules,
            self.technology_rules,
        )
        self.buildings = BuildingSystem(
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.laws = LawSystem(
            self.law_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.technologies = TechnologySystem(
            self.technology_rules,
            self.building_rules,
            self.survival_rules,
            self.law_rules,
        )
        self.events = EventSystem(
            self.event_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.oath_order = OathOrderSystem(
            self.oath_order_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.final_frost = FinalFrostSystem(
            self.final_frost_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.ending_report = EndingReportSystem()
        self.end_day = EndDayEngine(
            autosave_sink=self._capture_end_day_autosave
        )
        for system in (
            self.survival,
            self.buildings,
            self.laws,
            self.technologies,
            self.events,
            self.oath_order,
            self.final_frost,
        ):
            system.install(self.end_day)

        self._catalog = CommandCatalog()
        self._handlers: dict[str, Any] = {}
        for system in (
            self.end_day,
            self.survival,
            self.buildings,
            self.laws,
            self.technologies,
            self.events,
            self.oath_order,
            self.ending_report,
        ):
            for spec in system.command_specs():
                self._catalog.register(spec)
                self._handlers[spec.name] = system.execute
        self._validator = CommandValidator(self._catalog)
        self._validate_state()
        self._replay = ReplayLog(self._state)

    @classmethod
    def new(
        cls,
        *,
        config_dir: str | Path = "data",
        save_path: str | Path | None = None,
        seed: int = 0,
        overwrite: bool = False,
    ) -> GameSession:
        config_path = Path(config_dir)
        target = Path(save_path) if save_path is not None else None
        if target is not None and target.exists() and not overwrite:
            raise FileExistsError(f"save already exists: {target}")
        documents = cls._load_rule_documents(config_path)
        survival = load_survival_rules(
            config_path / _CONFIG_FILENAMES["survival"]
        )
        buildings = load_building_rules(
            config_path / _CONFIG_FILENAMES["buildings"]
        )
        state = create_initial_survival_state(
            survival,
            buildings,
            random_seed=seed,
        )
        session = cls(
            config_dir=config_path,
            state=state,
            save_path=target,
            rule_documents=documents,
        )
        session.events.initialize_day(session._state)
        session._validate_state()
        session._replay = ReplayLog(session._state)
        if target is not None:
            session.save()
        return session

    @classmethod
    def load(
        cls,
        save_path: str | Path,
        *,
        config_dir: str | Path = "data",
    ) -> GameSession:
        target = Path(save_path)
        document = json.loads(target.read_text(encoding="utf-8-sig"))
        state = decode_game_state(document)
        config_path = Path(config_dir)
        return cls(
            config_dir=config_path,
            state=state,
            save_path=target,
            rule_documents=cls._load_rule_documents(config_path),
        )

    @classmethod
    def open(
        cls,
        save_path: str | Path,
        *,
        config_dir: str | Path = "data",
        seed: int = 0,
    ) -> GameSession:
        target = Path(save_path)
        if target.exists():
            return cls.load(target, config_dir=config_dir)
        return cls.new(
            config_dir=config_dir,
            save_path=target,
            seed=seed,
        )

    @staticmethod
    def _load_rule_documents(
        config_dir: Path,
    ) -> dict[str, Mapping[str, Any]]:
        documents: dict[str, Mapping[str, Any]] = {}
        for section, filename in _CONFIG_FILENAMES.items():
            value = json.loads(
                (config_dir / filename).read_text(encoding="utf-8-sig")
            )
            if not isinstance(value, Mapping):
                raise TypeError(f"{filename} must contain a JSON object")
            documents[section] = value
        return documents

    @property
    def state(self) -> GameState:
        return deepcopy(self._state)

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def observe(self) -> Observation:
        return Observation.from_state(
            deepcopy(self._state),
            self.command_specs(),
            event_views=self.events.active_event_views(self._state),
            promise_views=self.events.active_promise_views(self._state),
            old_city_view=self.oath_order.old_city_view(self._state),
            oath_order_view=self.oath_order.route_view(self._state),
            final_frost_view=self.final_frost.observe(self._state),
            ending_report_view=self.ending_report.observe(self._state),
        )

    def status(self) -> dict[str, Any]:
        state = self._state
        population = state.population
        resources = state.resources
        final = state.final_result
        return {
            "state_sequence": state.command_sequence,
            "day": state.calendar.current_day,
            "max_day": state.calendar.max_day,
            "day_locked": state.calendar.is_day_locked,
            "run_state": final.run_state.value,
            "ending_id": final.ending_id,
            "hard_fail_type": (
                final.hard_fail_type.value
                if final.hard_fail_type is not None
                else None
            ),
            "population": {
                "alive": population.population_alive,
                "dead": population.population_dead,
                "workers": population.workers,
                "engineers": population.engineers,
                "children": population.children,
                "healthy": population.healthy_population,
                "sick": population.sick_population,
                "critical": population.critical_population,
                "disabled": population.disabled_population,
                "housed": population.housed_population,
                "homeless": population.homeless_population,
            },
            "resources": {
                "coal": resources.coal,
                "wood": resources.wood,
                "steel": resources.steel,
                "raw_food": resources.raw_food,
                "cooked_food": resources.cooked_food,
                "storage_used": storage_used(resources),
                "storage_capacity": resources.storage_capacity,
            },
            "furnace": {
                "mode_id": state.furnace.mode_id,
                "pressure": state.furnace.pressure,
                "overload_level": state.furnace.overload_level,
            },
            "trust": state.trust_panic.trust,
            "panic": state.trust_panic.panic,
            "research": {
                "active_tech_id": state.technologies.active_research_id,
                "progress_units": state.technologies.research_progress_units,
                "required_units": state.technologies.research_required_units,
            },
            "active_event_ids": sorted(state.events.active_events),
            "active_promise_ids": sorted(state.promises.active_promises),
            "pending_old_city_event_id": state.old_city.pending_event_id,
            "final_frost_active": self.final_frost_rules.is_frost_day(
                state.calendar.current_day
            ),
            "ending_report_available": final.report.is_generated,
        }

    def rules_view(self, section: str) -> dict[str, Any]:
        """Return one validated configuration document without recommendations."""

        if section not in self._rule_documents:
            raise KeyError(
                f"unknown rules section {section!r}; "
                f"expected one of {sorted(self._rule_documents)}"
            )
        return {
            "section": section,
            "config_status": self._rule_documents[section][
                "config_status"
            ],
            "document": deepcopy(self._rule_documents[section]),
        }

    def execute_payload(self, payload: Mapping[str, Any]) -> SessionExecution:
        if not isinstance(payload, Mapping):
            return self._malformed_result("")
        allowed = {
            "command_id",
            "name",
            "arguments",
            "expected_state_sequence",
        }
        if set(payload) - allowed:
            return self._malformed_result(
                str(payload.get("command_id", ""))
            )
        command_id = payload.get("command_id")
        if command_id is None:
            command_id = f"session-{self._attempt_sequence + 1:06d}"
        arguments = payload.get("arguments", {})
        if not isinstance(arguments, Mapping):
            return self._invalid_arguments_result(str(command_id))
        expected = payload.get(
            "expected_state_sequence",
            self._state.command_sequence,
        )
        request = CommandRequest(
            command_id=command_id,  # type: ignore[arg-type]
            name=payload.get("name"),  # type: ignore[arg-type]
            arguments=arguments,
            expected_state_sequence=expected,  # type: ignore[arg-type]
        )
        return self.execute(request)

    def command(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        command_id: str | None = None,
        expected_state_sequence: int | None = None,
    ) -> SessionExecution:
        return self.execute(
            CommandRequest(
                command_id=command_id
                or f"session-{self._attempt_sequence + 1:06d}",
                name=name,
                arguments=arguments or {},
                expected_state_sequence=(
                    self._state.command_sequence
                    if expected_state_sequence is None
                    else expected_state_sequence
                ),
            )
        )

    def execute(self, request: CommandRequest) -> SessionExecution:
        if not isinstance(request, CommandRequest):
            return self._malformed_result("")
        self._attempt_sequence += 1
        replay_sequence = self._attempt_sequence
        random_before = self._state.random
        # The target system owns stale-state and legality handling.  Keeping
        # those checks there preserves command-specific side effects such as
        # invalidating a consumed end-day confirmation token.
        validation = self._validator.validate(request)
        if not validation.is_valid:
            result = self._validation_result(request, validation)
            return self._finish_execution(
                request,
                result,
                random_before,
                (),
                (),
                replay_sequence,
                save_written=False,
            )

        before_document = encode_game_state(self._state)
        raw_result = self._handlers[request.name](self._state, request)
        if isinstance(raw_result, EndDayExecution):
            result = raw_result.result
            warnings = raw_result.warnings
            logs = raw_result.logs
        else:
            result = raw_result
            warnings = ()
            logs = (
                LogEntry(
                    1,
                    LogCategory.RESULT,
                    "session.command.result",
                    {
                        "name": request.name,
                        "accepted": result.accepted,
                        "code": result.code.value,
                    },
                ),
            )

        save_written = False
        if result.accepted and result.state_changed:
            try:
                self._validate_state()
                if self.save_path is not None:
                    self.save()
                    save_written = True
            except Exception as exc:
                self._state = decode_game_state(before_document)
                result = CommandResult(
                    command_id=request.command_id,
                    accepted=False,
                    code=ErrorCode.INTERNAL_ERROR,
                    state_changed=False,
                    state_sequence=self._state.command_sequence,
                    data={
                        "failed_stage": "session_save",
                        "exception_type": type(exc).__name__,
                    },
                )
                warnings = ()
                logs = (
                    LogEntry(
                        1,
                        LogCategory.SYSTEM,
                        "session.save.rolled_back",
                        {"name": request.name},
                    ),
                )
        return self._finish_execution(
            request,
            result,
            random_before,
            warnings,
            logs,
            replay_sequence,
            save_written=save_written,
        )

    def _finish_execution(
        self,
        request: CommandRequest,
        result: CommandResult,
        random_before: RandomState,
        warnings: tuple[RiskWarning, ...],
        logs: tuple[LogEntry, ...],
        replay_sequence: int,
        *,
        save_written: bool,
    ) -> SessionExecution:
        recorded_sequence: int | None = None
        if (
            isinstance(request.command_id, str)
            and isinstance(request.name, str)
            and isinstance(request.arguments, Mapping)
            and result.command_id == request.command_id
        ):
            try:
                self._replay.append(
                    ReplayEntry(
                        sequence=replay_sequence,
                        request=request,
                        result=result,
                        random_before=random_before,
                        random_after=self._state.random,
                        logs=logs,
                    )
                )
                recorded_sequence = replay_sequence
            except (TypeError, ValueError):
                recorded_sequence = None
        return SessionExecution(
            protocol_version=PROTOCOL_VERSION,
            replay_sequence=recorded_sequence,
            result=result,
            status=self.status(),
            warnings=warnings,
            save_written=save_written,
        )

    def _malformed_result(self, command_id: str) -> SessionExecution:
        return SessionExecution(
            protocol_version=PROTOCOL_VERSION,
            replay_sequence=None,
            result=CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INVALID_COMMAND_FORMAT,
                state_sequence=self._state.command_sequence,
            ),
            status=self.status(),
        )

    def _invalid_arguments_result(self, command_id: str) -> SessionExecution:
        return SessionExecution(
            protocol_version=PROTOCOL_VERSION,
            replay_sequence=None,
            result=CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INVALID_ARGUMENTS,
                state_sequence=self._state.command_sequence,
            ),
            status=self.status(),
        )

    def _validation_result(
        self,
        request: CommandRequest,
        validation: CommandValidation,
    ) -> CommandResult:
        return CommandResult(
            command_id=(
                request.command_id
                if isinstance(request.command_id, str)
                else ""
            ),
            accepted=False,
            code=validation.code,
            state_sequence=self._state.command_sequence,
            data=validation.details,
        )

    def replay_document(self) -> ReplayDocument:
        return self._replay.document()

    def write_replay(self, path: str | Path) -> None:
        self._write_document(Path(path), self.replay_document())

    def save(self) -> None:
        if self.save_path is None:
            raise ValueError("this session has no save path")
        self._validate_state()
        self._write_document(self.save_path, encode_game_state(self._state))

    @staticmethod
    def _write_document(path: Path, document: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(dumps(document))
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    def _capture_end_day_autosave(self, record: Any) -> None:
        self._last_end_day_autosave = deepcopy(record)

    def _validate_state(self) -> None:
        validate_game_state(
            self._state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.laws.validate_state(self._state)
        self.events.validate_state(self._state)
        self.oath_order.validate_state(self._state)
        self.final_frost.validate_state(self._state)
        self.ending_report.validate_state(self._state)
