from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEPRECATED_KEYS = frozenset(
    {
        "terminal_fail",
        "trust_fail",
        "panic_fail",
        "hope_state",
    }
)

PLACEHOLDER_VALUES = frozenset(
    {
        "DEPRECATED",
        "PENDING",
        "TODO_TEXT",
        "TODO_VALUE",
        "TODO_SYSTEM",
        "待判定",
        "待确认",
    }
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: Path
    location: str
    message: str

    def __str__(self) -> str:
        suffix = f" ({self.location})" if self.location else ""
        return f"{self.path}{suffix}: {self.message}"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    files_checked: int
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


def _walk(value: Any, location: str = "$") -> Iterator[tuple[str, Any]]:
    yield location, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{location}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from _walk(child, f"{location}[{index}]")


def _validate_value(path: Path, data: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for location, value in _walk(data):
        if isinstance(value, Mapping):
            for key in value:
                if key in DEPRECATED_KEYS:
                    issues.append(
                        ValidationIssue(
                            path,
                            f"{location}.{key}",
                            "作废字段不得进入运行配置",
                        )
                    )
        elif isinstance(value, str):
            marker = value.strip()
            if marker in PLACEHOLDER_VALUES or marker.startswith("PENDING_"):
                issues.append(
                    ValidationIssue(
                        path,
                        location,
                        f"非运行状态 {marker!r} 不得进入运行配置",
                    )
                )
    return issues


def validate_config_file(path: Path) -> list[ValidationIssue]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [ValidationIssue(path, "", f"文件不是有效 UTF-8：{exc}")]
    except OSError as exc:
        return [ValidationIssue(path, "", f"无法读取文件：{exc}")]

    try:
        data = json.loads(source)
    except json.JSONDecodeError as exc:
        return [
            ValidationIssue(
                path,
                f"line {exc.lineno}, column {exc.colno}",
                f"JSON 格式错误：{exc.msg}",
            )
        ]
    return _validate_value(path, data)


def validate_config_tree(root: Path) -> ValidationReport:
    root = Path(root)
    if not root.is_dir():
        issue = ValidationIssue(root, "", "配置目录不存在或不是目录")
        return ValidationReport(files_checked=0, issues=(issue,))

    config_files = sorted(root.rglob("*.json"))
    issues: list[ValidationIssue] = []
    for path in config_files:
        issues.extend(validate_config_file(path))
    return ValidationReport(
        files_checked=len(config_files),
        issues=tuple(issues),
    )
