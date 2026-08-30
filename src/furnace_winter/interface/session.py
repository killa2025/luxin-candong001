from __future__ import annotations

import json
import math
import os
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from furnace_winter.config import (
    load_building_rules,
    load_event_rules,
    load_final_frost_rules,
    load_law_rules,
    load_map_rules,
    load_oath_order_rules,
    load_survival_rules,
    load_technology_rules,
)
from furnace_winter.gameplay import (
    AUTOSAVE_END_DAY_SLOT,
    AutosaveRecord,
    BuildingSystem,
    EndDayEngine,
    EndDayExecution,
    EndingReportSystem,
    EventSystem,
    FinalFrostSystem,
    LawSystem,
    MapSystem,
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
    invalid_arguments_format_details,
    invalid_command_format_details,
)
from furnace_winter.interface.feedback import CommandResult
from furnace_winter.interface.observation import Observation, PROTOCOL_VERSION
from furnace_winter.interface.replay import (
    decode_log_entry,
    decode_replay_document,
    EventLog,
    LogCategory,
    LogEntry,
    ReplayDocument,
    ReplayEntry,
    ReplayLog,
)
from furnace_winter.models import (
    FINAL_DAY,
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
    "maps": "maps.json",
    "technologies": "technologies.json",
    "events": "events.json",
    "oath_order": "oath_order.json",
    "final_frost": "final_frost.json",
}

_AUTOSAVE_RESUME_STAGES = (
    "advance_day",
    "terminal_state",
    "final_settlement",
)


class _NonFiniteJsonNumber(ValueError):
    pass


def _parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise _NonFiniteJsonNumber(value)
    return parsed


def _reject_non_finite_json_constant(value: str) -> None:
    raise _NonFiniteJsonNumber(value)


def _safe_diagnostic_value(value: Any) -> Any:
    """Return a value that the formal serializer can always emit."""

    try:
        return json.loads(dumps(value))
    except (TypeError, ValueError):
        return {
            "value_not_serializable": True,
            "python_type": type(value).__name__,
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


@dataclass(frozen=True, slots=True)
class _FileSnapshot:
    path: Path
    existed: bool
    content: bytes | None


class AutosaveSnapshotPathError(ValueError):
    """Raised when an end-day snapshot is used as a primary save path."""

    code = "AUTOSAVE_SNAPSHOT_NOT_PRIMARY_SAVE"

    def __init__(self, path: Path) -> None:
        candidates = self._primary_save_candidates(path)
        recognized = tuple(
            candidate
            for candidate in candidates
            if self._is_recognized_primary_save(candidate)
        )
        candidate = recognized[0] if len(recognized) == 1 else None
        resolution = (
            "resolved"
            if candidate is not None
            else "ambiguous"
            if len(recognized) > 1
            else "not_found"
        )
        self.details = {
            "reason": "end_day_autosave_snapshot_is_not_primary_save",
            "provided_document_type": "end_day_autosave_snapshot",
            "provided_path_role": "autosave_end_day",
            "accepted_as_primary_save": False,
            "inspect_request_after_opening_primary_save": {"type": "autosave"},
            "recovery": {
                "open_primary_save_path": (
                    str(candidate) if candidate is not None else None
                ),
                "primary_save_path_resolution": resolution,
                "primary_save_path_ambiguous": len(recognized) > 1,
                "primary_save_path_candidates": [
                    str(candidate) for candidate in candidates
                ],
                "recognized_primary_save_paths": [
                    str(candidate) for candidate in recognized
                ],
                "open_primary_save_instead": True,
                "do_not_extract_nested_state": True,
            },
        }
        super().__init__(self.details["reason"])

    @staticmethod
    def _primary_save_candidates(path: Path) -> tuple[Path, ...]:
        marker = f".{AUTOSAVE_END_DAY_SLOT}"
        if not path.stem.endswith(marker):
            return ()
        primary_stem = path.stem[: -len(marker)]
        if not primary_stem:
            return ()
        candidates = [path.with_name(f"{primary_stem}{path.suffix}")]
        if path.suffix.casefold() == ".json":
            candidates.insert(0, path.with_name(primary_stem))
        return tuple(dict.fromkeys(candidates))

    @staticmethod
    def _is_recognized_primary_save(path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            decode_game_state(document)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return False
        return True


class AutosaveSnapshotValidationError(ValueError):
    """Stable machine-readable diagnosis for a damaged end-day snapshot."""

    code = "AUTOSAVE_SNAPSHOT_INVALID"

    def __init__(
        self,
        path: Path | None,
        *,
        field: str,
        reason: str,
        constraint: str,
        actual_value: Any = None,
        expected_value: Any = None,
        allowed_values: tuple[str, ...] = (),
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.details = {
            "reason": reason,
            "document_type": "end_day_autosave_snapshot",
            "path_role": "autosave_end_day",
            "path": str(path) if path is not None else None,
            "field": field,
            "constraint": constraint,
            "actual_value": _safe_diagnostic_value(actual_value),
            "expected_value": _safe_diagnostic_value(expected_value),
            "allowed_values": list(allowed_values),
            "context": _safe_diagnostic_value(dict(context or {})),
        }
        super().__init__(reason)


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
        self._ensure_save_target_is_not_config(config_dir, save_path)
        self.config_dir = config_dir
        self.save_path = save_path
        self._config_source_paths = frozenset(
            self._path_identity(path)
            for path in self._runtime_config_paths(config_dir)
        )
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
        self.map_rules = load_map_rules(
            config_dir / _CONFIG_FILENAMES["maps"]
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
        self.buildings.synchronize_forced_shutdown_state(self._state)
        self.laws = LawSystem(
            self.law_rules,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.maps = MapSystem(self.map_rules, self.building_rules)
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
            self.maps,
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
        map_mode: str = "random",
        map_key: str | None = None,
        overwrite: bool = False,
    ) -> GameSession:
        config_path = Path(config_dir)
        target = Path(save_path) if save_path is not None else None
        cls._ensure_save_target_is_not_config(config_path, target)
        if target is not None and target.exists():
            try:
                existing_document = json.loads(
                    target.read_text(encoding="utf-8-sig")
                )
            except (OSError, UnicodeError, json.JSONDecodeError):
                existing_document = None
            if cls._is_end_day_autosave_document(existing_document):
                raise AutosaveSnapshotPathError(target)
        if target is not None and not overwrite:
            existing_paths = tuple(
                path
                for path in (target, cls._autosave_path_for(target))
                if path.exists()
            )
            if existing_paths:
                raise FileExistsError(
                    "session persistence already exists: "
                    + ", ".join(str(path) for path in existing_paths)
                )
        documents = cls._load_rule_documents(config_path)
        survival = load_survival_rules(
            config_path / _CONFIG_FILENAMES["survival"]
        )
        buildings = load_building_rules(
            config_path / _CONFIG_FILENAMES["buildings"]
        )
        maps = load_map_rules(
            config_path / _CONFIG_FILENAMES["maps"]
        )
        state = create_initial_survival_state(
            survival,
            buildings,
            random_seed=seed,
            map_rules=maps,
            map_selection_mode=map_mode,
            map_key=map_key,
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
            session._write_new_session_persistence()
        return session

    @classmethod
    def load(
        cls,
        save_path: str | Path,
        *,
        config_dir: str | Path = "data",
    ) -> GameSession:
        target = Path(save_path)
        document = cls.read_primary_save_document(target)
        state = decode_game_state(document)
        config_path = Path(config_dir)
        return cls(
            config_dir=config_path,
            state=state,
            save_path=target,
            rule_documents=cls._load_rule_documents(config_path),
        )

    @classmethod
    def read_primary_save_document(cls, path: str | Path) -> Any:
        """Read a primary save while rejecting the separate autosave envelope."""

        target = Path(path)
        document = json.loads(target.read_text(encoding="utf-8-sig"))
        if cls._is_end_day_autosave_document(document):
            raise AutosaveSnapshotPathError(target)
        return document

    @staticmethod
    def _is_end_day_autosave_document(document: Any) -> bool:
        return (
            isinstance(document, Mapping)
            and document.get("slot") == AUTOSAVE_END_DAY_SLOT
            and isinstance(document.get("state"), Mapping)
            and "resume_stage" in document
            and "settled_day" in document
            and "logs" in document
        )

    @classmethod
    def open(
        cls,
        save_path: str | Path,
        *,
        config_dir: str | Path = "data",
        seed: int = 0,
        map_mode: str = "random",
        map_key: str | None = None,
    ) -> GameSession:
        target = Path(save_path)
        if target.exists():
            return cls.load(target, config_dir=config_dir)
        return cls.new(
            config_dir=config_dir,
            save_path=target,
            seed=seed,
            map_mode=map_mode,
            map_key=map_key,
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

    @property
    def autosave_path(self) -> Path | None:
        if self.save_path is None:
            return None
        return self._autosave_path_for(self.save_path)

    @staticmethod
    def _autosave_path_for(save_path: Path) -> Path:
        suffix = save_path.suffix or ".json"
        stem = (
            save_path.name[: -len(save_path.suffix)]
            if save_path.suffix
            else save_path.name
        )
        return save_path.with_name(
            f"{stem}.{AUTOSAVE_END_DAY_SLOT}{suffix}"
        )

    def command_specs(self) -> tuple[CommandSpec, ...]:
        return self._catalog.specs()

    def observe(self) -> Observation:
        return Observation.from_state(
            deepcopy(self._state),
            self.command_specs(),
            available_rule_sections=tuple(sorted(self._rule_documents)),
            protocol_contract=self._protocol_contract(),
            event_views=self.events.active_event_views(self._state),
            promise_views=self.events.active_promise_views(self._state),
            map_view=self.maps.view(self._state),
            law_view=self.laws.observe(self._state),
            technology_view=self.technologies.view(self._state),
            old_city_view=self.oath_order.old_city_view(self._state),
            oath_order_view=self.oath_order.route_view(self._state),
            final_frost_view=self.final_frost.observe(self._state),
            ending_report_view=self.ending_report.observe(self._state),
        )

    def _protocol_contract(self) -> dict[str, Any]:
        rule_sections = tuple(sorted(self._rule_documents))
        return {
            "play_envelopes": {
                "supported_types": [
                    "autosave",
                    "command",
                    "command_specs",
                    "observe",
                    "quit",
                    "replay",
                    "rules",
                    "status",
                ],
                "status_request_shape": {"type": "status"},
                "command_specs_request_shape": {"type": "command_specs"},
                "autosave_request_shape": {"type": "autosave"},
                "contains_strategy_recommendations": False,
            },
            "rules_query": {
                "request_shape": {
                    "type": "rules",
                    "section": "RULE_SECTION_STRING",
                },
                "available_sections": list(rule_sections),
                "returns_validated_configuration": True,
                "contains_strategy_recommendations": False,
            },
            "end_day_confirmation": self.end_day.confirmation_lifecycle(),
            "sequence_semantics": {
                "replay_sequence": {
                    "scope": "current_game_session",
                    "persistence": "not_saved",
                    "assigned_to": "recorded_command_attempts",
                    "includes_rejected_commands": True,
                    "may_be_null_when_attempt_is_not_recorded": True,
                    "resets_when_session_opens": True,
                    "use_for_optimistic_concurrency": False,
                },
                "state_sequence": {
                    "scope": "persistent_game_state",
                    "persistence": "saved_in_game_state",
                    "increments_on": "committed_state_changes_only",
                    "includes_rejected_commands": False,
                    "resets_when_session_opens": False,
                    "request_field": "expected_state_sequence",
                    "use_for_optimistic_concurrency": True,
                },
            },
            "persistence_files": self._persistence_contract(),
        }

    def _persistence_contract(self) -> dict[str, Any]:
        return {
            "primary_save": {
                "document_type": "game_state",
                "role": "resumable_primary_save",
                "accepted_by": ["play", "report"],
                "contains_current_committed_state": True,
            },
            "autosave_end_day": {
                "document_type": "end_day_autosave_snapshot",
                "role": "pre_advance_transaction_snapshot",
                "slot": AUTOSAVE_END_DAY_SLOT,
                "boundary": "after_daily_cleanup_before_date_advance",
                "contains_state_logs_and_resume_stage": True,
                "replaces_primary_save": False,
                "accepted_as_primary_save": False,
                "view_request_shape": {"type": "autosave"},
                "inspect_after_opening_primary_save": True,
                "extract_nested_state_for_play": False,
            },
        }

    def autosave_view(self) -> dict[str, Any]:
        """Return the latest end-day snapshot through its read-only envelope."""

        contract = self._persistence_contract()["autosave_end_day"]
        record: AutosaveRecord | None = None
        source = "none"
        target = self.autosave_path
        if target is not None and target.exists():
            record = self._read_end_day_autosave(target)
            source = "disk"
        elif self._last_end_day_autosave is not None:
            record = deepcopy(self._last_end_day_autosave)
            source = "memory"
        if record is None:
            return {
                "available": False,
                "document_type": "end_day_autosave_snapshot",
                "slot": AUTOSAVE_END_DAY_SLOT,
                "source": source,
                "contract": contract,
            }
        try:
            snapshot_state = decode_game_state(record.state)
            self._validate_state_value(snapshot_state)
        except (TypeError, ValueError) as exc:
            raise AutosaveSnapshotValidationError(
                target,
                field="state",
                reason="nested_game_state_invalid",
                constraint="must be a complete valid game state",
                context={"validation_exception_type": type(exc).__name__},
            ) from exc
        self._validate_end_day_autosave(record, snapshot_state, target)
        return {
            "available": True,
            "document_type": "end_day_autosave_snapshot",
            "slot": record.slot,
            "source": source,
            "settled_day": record.settled_day,
            "resume_stage": record.resume_stage,
            "state": deepcopy(record.state),
            "logs": deepcopy(record.logs),
            "contract": contract,
        }

    @staticmethod
    def _read_end_day_autosave(path: Path) -> AutosaveRecord:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise AutosaveSnapshotValidationError(
                path,
                field="$",
                reason="invalid_text_encoding",
                constraint="must be UTF-8 or UTF-8 with BOM",
                context={"decoding_exception_type": type(exc).__name__},
            ) from exc
        try:
            document = json.loads(
                text,
                parse_float=_parse_finite_json_float,
                parse_constant=_reject_non_finite_json_constant,
            )
        except _NonFiniteJsonNumber as exc:
            raise AutosaveSnapshotValidationError(
                path,
                field="$",
                reason="invalid_json",
                constraint="all JSON numbers must be finite",
                context={"parse_reason": "non_finite_number"},
            ) from exc
        except json.JSONDecodeError as exc:
            raise AutosaveSnapshotValidationError(
                path,
                field="$",
                reason="invalid_json",
                constraint="must contain one valid JSON document",
                context={"line": exc.lineno, "column": exc.colno},
            ) from exc
        except ValueError as exc:
            raise AutosaveSnapshotValidationError(
                path,
                field="$",
                reason="invalid_json",
                constraint="all JSON numeric values must be supported",
                context={"parse_reason": "numeric_value_unsupported"},
            ) from exc
        if not isinstance(document, Mapping):
            raise AutosaveSnapshotValidationError(
                path,
                field="$",
                reason="document_not_object",
                constraint="top-level value must be an OBJECT",
                actual_value=type(document).__name__,
                expected_value="OBJECT",
            )
        expected = frozenset(
            {"slot", "settled_day", "state", "logs", "resume_stage"}
        )
        if frozenset(document) != expected:
            raise AutosaveSnapshotValidationError(
                path,
                field="$",
                reason="top_level_fields_invalid",
                constraint="top-level fields must match the autosave envelope exactly",
                actual_value={
                    "missing": sorted(expected - frozenset(document)),
                    "unexpected": sorted(frozenset(document) - expected),
                },
                expected_value=sorted(expected),
            )
        if document["slot"] != AUTOSAVE_END_DAY_SLOT:
            raise AutosaveSnapshotValidationError(
                path,
                field="slot",
                reason="slot_invalid",
                constraint="must identify the formal end-day autosave slot",
                actual_value=document["slot"],
                expected_value=AUTOSAVE_END_DAY_SLOT,
            )
        settled_day = document["settled_day"]
        if (
            not isinstance(settled_day, int)
            or isinstance(settled_day, bool)
            or settled_day < 1
        ):
            raise AutosaveSnapshotValidationError(
                path,
                field="settled_day",
                reason="settled_day_invalid",
                constraint="must be a positive INTEGER",
                actual_value=settled_day,
            )
        if not isinstance(document["state"], Mapping):
            raise AutosaveSnapshotValidationError(
                path,
                field="state",
                reason="nested_game_state_not_object",
                constraint="must be a complete game-state OBJECT",
                actual_value=type(document["state"]).__name__,
                expected_value="OBJECT",
            )
        resume_stage = document["resume_stage"]
        if not isinstance(resume_stage, str) or not resume_stage.strip():
            raise AutosaveSnapshotValidationError(
                path,
                field="resume_stage",
                reason="resume_stage_invalid_type",
                constraint="must be a non-empty STRING",
                actual_value=resume_stage,
                allowed_values=_AUTOSAVE_RESUME_STAGES,
            )
        logs = document["logs"]
        if not isinstance(logs, list):
            raise AutosaveSnapshotValidationError(
                path,
                field="logs",
                reason="logs_not_array",
                constraint="must be an ARRAY of structured log entries",
                actual_value=type(logs).__name__,
                expected_value="ARRAY",
            )
        event_log = EventLog()
        previous_sequence: int | None = None
        for index, item in enumerate(logs):
            try:
                entry = decode_log_entry(item)
            except (TypeError, ValueError) as exc:
                raise AutosaveSnapshotValidationError(
                    path,
                    field=f"logs[{index}]",
                    reason="log_entry_invalid",
                    constraint="must be a valid structured log entry",
                    context={"validation_exception_type": type(exc).__name__},
                ) from exc
            if previous_sequence is not None and entry.sequence <= previous_sequence:
                raise AutosaveSnapshotValidationError(
                    path,
                    field=f"logs[{index}].sequence",
                    reason="log_sequence_not_strictly_increasing",
                    constraint="must be greater than the previous log sequence",
                    actual_value=entry.sequence,
                    context={"previous_sequence": previous_sequence},
                )
            event_log.append(entry)
            previous_sequence = entry.sequence
        return AutosaveRecord(
            slot=document["slot"],
            settled_day=settled_day,
            state=document["state"],
            logs=event_log.entries(),
            resume_stage=resume_stage,
        )

    @staticmethod
    def _validate_end_day_autosave(
        record: AutosaveRecord,
        state: GameState,
        path: Path | None,
    ) -> None:
        if (
            record.settled_day != state.calendar.current_day
            or record.settled_day != state.daily_survival.settled_day
        ):
            raise AutosaveSnapshotValidationError(
                path,
                field="settled_day",
                reason="settled_day_state_mismatch",
                constraint="must equal both settled-day fields in the nested state",
                actual_value=record.settled_day,
                expected_value={
                    "state.calendar.current_day": state.calendar.current_day,
                    "state.daily_survival.settled_day": (
                        state.daily_survival.settled_day
                    ),
                },
            )
        if not state.calendar.is_day_locked or not state.calendar.is_end_day_confirmed:
            raise AutosaveSnapshotValidationError(
                path,
                field="state.calendar",
                reason="settlement_boundary_not_locked",
                constraint="snapshot state must be locked and end-day-confirmed",
                actual_value={
                    "is_day_locked": state.calendar.is_day_locked,
                    "is_end_day_confirmed": state.calendar.is_end_day_confirmed,
                },
                expected_value={
                    "is_day_locked": True,
                    "is_end_day_confirmed": True,
                },
            )
        if record.resume_stage not in _AUTOSAVE_RESUME_STAGES:
            raise AutosaveSnapshotValidationError(
                path,
                field="resume_stage",
                reason="resume_stage_unknown",
                constraint="must be one of the formal resume-stage values",
                actual_value=record.resume_stage,
                allowed_values=_AUTOSAVE_RESUME_STAGES,
            )
        expected_stage = (
            "terminal_state"
            if state.final_result.hard_fail_type is not None
            else "final_settlement"
            if record.settled_day == FINAL_DAY
            else "advance_day"
        )
        if record.resume_stage != expected_stage:
            raise AutosaveSnapshotValidationError(
                path,
                field="resume_stage",
                reason="resume_stage_state_mismatch",
                constraint="must match the nested state's settlement outcome",
                actual_value=record.resume_stage,
                expected_value=expected_stage,
                allowed_values=_AUTOSAVE_RESUME_STAGES,
            )

    def status(self) -> dict[str, Any]:
        state = self._state
        population = state.population
        resources = state.resources
        final = state.final_result
        law_view = self.laws.observe(state)
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
            "hunger": {
                "none": state.hunger.none_population,
                "light": state.hunger.light_population,
                "severe": state.hunger.severe_population,
                "starving": state.hunger.starving_population,
                "total_hunger_days": state.hunger.total_hunger_days,
                "total_unfed_person_days": (
                    state.hunger.total_unfed_person_days
                ),
                "peak_unfed_count": state.hunger.peak_unfed_count,
                "peak_unfed_ratio": {
                    "numerator": state.hunger.peak_unfed_count,
                    "denominator": (
                        state.hunger.peak_unfed_population_start
                    ),
                },
                "hunger_deaths_total": state.hunger.hunger_deaths_total,
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
            "ration": {
                "selected_mode": law_view["ration_mode"],
                "effective_mode": law_view["effective_ration_mode"],
                "fallback_reason": law_view["ration_fallback_reason"],
                "last_settled_mode": state.daily_survival.ration_mode_used,
                "last_settled_day": state.daily_survival.settled_day,
            },
            "trust": state.trust_panic.trust,
            "panic": state.trust_panic.panic,
            "map": self.maps.view(state),
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
            "persistence": {
                "primary_save_configured": self.save_path is not None,
                "autosave_end_day_present": (
                    self._last_end_day_autosave is not None
                    or (
                        self.autosave_path is not None
                        and self.autosave_path.exists()
                    )
                ),
                "autosave_end_day_is_primary_save": False,
                "autosave_end_day_view_request": {"type": "autosave"},
            },
        }

    def rules_view(self, section: str) -> dict[str, Any]:
        """Return one validated configuration document without recommendations."""

        if section not in self._rule_documents:
            raise KeyError(
                f"unknown rules section {section!r}; "
                f"expected one of {sorted(self._rule_documents)}"
            )
        result = {
            "section": section,
            "config_status": self._rule_documents[section][
                "config_status"
            ],
            "document": deepcopy(self._rule_documents[section]),
        }
        if section == "technologies":
            result["interface_text"] = {
                "research_start": self.technologies.research_start_notice(),
                "descriptions": self.technologies.description_catalog(),
            }
        elif section == "oath_order":
            result["interface_text"] = self.oath_order.route_view(self._state)
        return result

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
            return self._malformed_result(
                str(command_id),
                invalid_arguments_format_details(arguments),
            )
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
        end_day_runtime_before = self.end_day.snapshot_runtime()
        captured_autosave_before = deepcopy(self._last_end_day_autosave)
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

        result = self._with_protocol_guidance(request, result)

        save_written = False
        file_snapshots: tuple[_FileSnapshot, ...] = ()
        if result.accepted and result.state_changed:
            try:
                self._validate_state()
                if self.save_path is not None:
                    paths_to_snapshot = [self.save_path]
                    if (
                        isinstance(raw_result, EndDayExecution)
                        and raw_result.autosave is not None
                    ):
                        autosave_path = self.autosave_path
                        if autosave_path is None:
                            raise RuntimeError("autosave path is unavailable")
                        paths_to_snapshot.append(autosave_path)
                    file_snapshots = tuple(
                        self._snapshot_file(path)
                        for path in paths_to_snapshot
                    )
                    if (
                        isinstance(raw_result, EndDayExecution)
                        and raw_result.autosave is not None
                    ):
                        self._write_end_day_autosave(raw_result.autosave)
                    self.save()
                    save_written = True
            except Exception as exc:
                self._state = decode_game_state(before_document)
                self.end_day.restore_runtime(end_day_runtime_before)
                self._last_end_day_autosave = captured_autosave_before
                rollback_exception_type = self._restore_files(file_snapshots)
                error_data = {
                    "failed_stage": "session_save",
                    "exception_type": type(exc).__name__,
                }
                if rollback_exception_type is not None:
                    error_data["rollback_exception_type"] = (
                        rollback_exception_type
                    )
                result = CommandResult(
                    command_id=request.command_id,
                    accepted=False,
                    code=ErrorCode.INTERNAL_ERROR,
                    state_changed=False,
                    state_sequence=self._state.command_sequence,
                    data=error_data,
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

    def _malformed_result(
        self,
        command_id: str,
        details: Mapping[str, Any] | None = None,
    ) -> SessionExecution:
        return SessionExecution(
            protocol_version=PROTOCOL_VERSION,
            replay_sequence=None,
            result=CommandResult(
                command_id=command_id,
                accepted=False,
                code=ErrorCode.INVALID_COMMAND_FORMAT,
                state_sequence=self._state.command_sequence,
                data=(
                    invalid_command_format_details()
                    if details is None
                    else dict(details)
                ),
            ),
            status=self.status(),
        )

    def _validation_result(
        self,
        request: CommandRequest,
        validation: CommandValidation,
    ) -> CommandResult:
        return self._with_protocol_guidance(
            request,
            CommandResult(
                command_id=(
                    request.command_id
                    if isinstance(request.command_id, str)
                    else ""
                ),
                accepted=False,
                code=validation.code,
                state_sequence=self._state.command_sequence,
                data=validation.details,
            ),
        )

    def _with_protocol_guidance(
        self,
        request: CommandRequest,
        result: CommandResult,
    ) -> CommandResult:
        if result.accepted:
            return result
        data = dict(result.data)
        if result.code is ErrorCode.STALE_STATE:
            data.setdefault("reason", "state_sequence_mismatch")
            data["current_state_sequence"] = self._state.command_sequence
            data["requires_fresh_observation"] = True
            data["retry_expected_state_sequence"] = (
                self._state.command_sequence
            )
            if request.expected_state_sequence is not None:
                data.setdefault(
                    "submitted_expected_state_sequence",
                    request.expected_state_sequence,
                )
        if result.code is ErrorCode.COMMAND_NOT_REGISTERED:
            data.setdefault("reason", "command_name_not_registered")
            data.setdefault("submitted_name", request.name)
            if request.name == "rules.query":
                data.update(
                    {
                        "rules_query_is_game_command": False,
                        "rules_query_contract": deepcopy(
                            self._protocol_contract()["rules_query"]
                        ),
                    }
                )
        if data.get("reason") == "confirmation_required":
            data.update(
                {
                    "required_confirmation_value": True,
                    "confirm_false_is_preview": False,
                    "state_will_change": False,
                }
            )
        if (
            request.name == "game.triage"
            and result.code is ErrorCode.INVALID_ARGUMENTS
            and "building_id"
            in {
                *data.get("missing", []),
                *data.get("wrong_types", []),
            }
        ):
            contract = self.laws.triage_target_contract()
            data.update(
                {
                    "requirement_text_id": contract[
                        "requirement_text_id"
                    ],
                    "requirement_text": contract["requirement_text"],
                }
            )
        if data == dict(result.data):
            return result
        return replace(result, data=data)

    def replay_document(self) -> ReplayDocument:
        return self._replay.document()

    def write_replay(
        self,
        path: str | Path,
        *,
        overwrite: bool = False,
    ) -> None:
        target = Path(path)
        self._ensure_replay_target_is_safe(target)
        if target.exists():
            if not overwrite:
                raise FileExistsError(f"replay already exists: {target}")
            if not self._is_replay_document(target):
                raise ValueError(
                    "overwrite target is not a valid replay document"
                )
        self._write_document(target, self.replay_document())

    def save(self) -> None:
        if self.save_path is None:
            raise ValueError("this session has no save path")
        self._ensure_save_target_is_not_config(
            self.config_dir,
            self.save_path,
        )
        self._validate_state()
        self._write_document(self.save_path, encode_game_state(self._state))

    def _write_end_day_autosave(self, record: AutosaveRecord) -> None:
        if not isinstance(record, AutosaveRecord):
            raise TypeError("record must be AutosaveRecord")
        target = self.autosave_path
        if target is None:
            raise ValueError("this session has no autosave path")
        self._write_document(target, record)

    def _write_new_session_persistence(self) -> None:
        if self.save_path is None:
            raise ValueError("this session has no save path")
        autosave_path = self.autosave_path
        if autosave_path is None:
            raise RuntimeError("autosave path is unavailable")
        snapshots = tuple(
            self._snapshot_file(path)
            for path in (self.save_path, autosave_path)
        )
        try:
            self.save()
            self._remove_end_day_autosave()
        except Exception as exc:
            rollback_exception_type = self._restore_files(snapshots)
            if rollback_exception_type is not None:
                raise RuntimeError(
                    "new session persistence rollback failed: "
                    f"{rollback_exception_type}"
                ) from exc
            raise

    def _remove_end_day_autosave(self) -> None:
        target = self.autosave_path
        if target is None:
            raise ValueError("this session has no autosave path")
        target.unlink(missing_ok=True)

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

    @staticmethod
    def _runtime_config_paths(config_dir: Path) -> tuple[Path, ...]:
        return (
            config_dir / "manifest.json",
            *(
                config_dir / filename
                for filename in _CONFIG_FILENAMES.values()
            ),
        )

    @staticmethod
    def _path_identity(path: Path) -> str:
        return os.path.normcase(str(path.resolve(strict=False)))

    @classmethod
    def _ensure_save_target_is_not_config(
        cls,
        config_dir: Path,
        save_path: Path | None,
    ) -> None:
        if save_path is None:
            return
        target_identity = cls._path_identity(save_path)
        if any(
            target_identity == cls._path_identity(config_path)
            for config_path in cls._runtime_config_paths(config_dir)
        ):
            raise ValueError("save path conflicts with a runtime config file")

    def _ensure_replay_target_is_safe(self, target: Path) -> None:
        target_identity = self._path_identity(target)
        protected_paths = set(self._config_source_paths)
        if self.save_path is not None:
            protected_paths.add(self._path_identity(self.save_path))
        if self.autosave_path is not None:
            protected_paths.add(self._path_identity(self.autosave_path))
        if target_identity in protected_paths:
            raise ValueError(
                "replay path conflicts with a protected session file"
            )

    @staticmethod
    def _is_replay_document(path: Path) -> bool:
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            decode_replay_document(document)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return True

    @staticmethod
    def _snapshot_file(path: Path) -> _FileSnapshot:
        if not path.exists():
            return _FileSnapshot(path=path, existed=False, content=None)
        if not path.is_file():
            raise ValueError(f"persistence target is not a file: {path}")
        return _FileSnapshot(
            path=path,
            existed=True,
            content=path.read_bytes(),
        )

    @classmethod
    def _restore_files(
        cls,
        snapshots: tuple[_FileSnapshot, ...],
    ) -> str | None:
        first_exception_type: str | None = None
        for snapshot in reversed(snapshots):
            try:
                if snapshot.existed:
                    if snapshot.content is None:
                        raise RuntimeError("file snapshot content is missing")
                    cls._write_bytes(snapshot.path, snapshot.content)
                else:
                    snapshot.path.unlink(missing_ok=True)
            except Exception as exc:
                if first_exception_type is None:
                    first_exception_type = type(exc).__name__
        return first_exception_type

    @staticmethod
    def _write_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    def _validate_state(self) -> None:
        self._validate_state_value(self._state)

    def _validate_state_value(self, state: GameState) -> None:
        validate_game_state(
            state,
            self.building_rules,
            self.survival_rules,
            self.technology_rules,
        )
        self.laws.validate_state(state)
        self.maps.validate_state(state)
        self.events.validate_state(state)
        self.oath_order.validate_state(state)
        self.final_frost.validate_state(state)
        self.ending_report.validate_state(state)
