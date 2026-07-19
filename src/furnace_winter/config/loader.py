from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from furnace_winter.config.status import ConfigStatus
from furnace_winter.config.validator import ValidationIssue, validate_config_file, validate_config_tree


class ConfigLoadError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(str(issue) for issue in issues))


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    path: Path
    data: Mapping[str, Any]
    status: ConfigStatus | None


def load_config_file(path: Path) -> LoadedConfig:
    path = Path(path)
    issues = tuple(validate_config_file(path))
    if issues:
        raise ConfigLoadError(issues)

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, Mapping):
        raise ConfigLoadError(
            (ValidationIssue(path, "$", "配置文件顶层必须是 JSON 对象"),)
        )

    raw_status = data.get("config_status")
    try:
        status = ConfigStatus(raw_status) if raw_status is not None else None
    except ValueError as exc:
        raise ConfigLoadError(
            (ValidationIssue(path, "$.config_status", f"未知配置状态：{raw_status!r}"),)
        ) from exc
    if status is not None and not status.is_runtime:
        raise ConfigLoadError(
            (ValidationIssue(path, "$.config_status", "非运行状态不得加载"),)
        )
    return LoadedConfig(path=path, data=dict(data), status=status)


def load_config_tree(root: Path) -> tuple[LoadedConfig, ...]:
    root = Path(root)
    report = validate_config_tree(root)
    if not report.is_valid:
        raise ConfigLoadError(report.issues)
    return tuple(load_config_file(path) for path in sorted(root.rglob("*.json")))
