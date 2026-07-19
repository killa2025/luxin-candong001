from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from furnace_winter.config.status import ConfigStatus


DEPRECATED_KEYS = frozenset(
    {
        "terminal_fail",
        "trust_fail",
        "panic_fail",
        "hope_state",
    }
)

NON_RUNTIME_MARKER_PATTERN = re.compile(
    r"^(?:"
    r"PENDING(?:_[A-Z][A-Z0-9_]*)?"
    r"|DEPRECATED"
    r"|TODO_(?:TEXT|VALUE|SYSTEM)"
    r"|待确认"
    r"|待判定"
    r")(?=$|[\s:：,，;；.!！?？\-–—/／(（\[【])"
)


class _NonFiniteNumberError(ValueError):
    def __init__(self, token: str) -> None:
        super().__init__(token)
        self.token = token


def _reject_non_finite_number(token: str) -> None:
    raise _NonFiniteNumberError(token)


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
                    continue
                marker = key.strip()
                if NON_RUNTIME_MARKER_PATTERN.match(marker):
                    issues.append(
                        ValidationIssue(
                            path,
                            f"{location}.{key}",
                            f"非运行标记字段 {marker!r} 不得进入运行配置",
                        )
                    )
        elif isinstance(value, str):
            marker = value.strip()
            if NON_RUNTIME_MARKER_PATTERN.match(marker):
                issues.append(
                    ValidationIssue(
                        path,
                        location,
                        f"非运行状态 {marker!r} 不得进入运行配置",
                    )
                )
    return issues


def _validate_document(path: Path, data: Any) -> list[ValidationIssue]:
    if not isinstance(data, Mapping):
        return [ValidationIssue(path, "$", "配置文件顶层必须是 JSON 对象")]

    issues: list[ValidationIssue] = []
    if "config_status" not in data:
        issues.append(
            ValidationIssue(path, "$.config_status", "运行配置必须声明 config_status")
        )
    else:
        raw_status = data["config_status"]
        if not isinstance(raw_status, str):
            issues.append(
                ValidationIssue(path, "$.config_status", "config_status 必须是字符串")
            )
        else:
            try:
                status = ConfigStatus(raw_status)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        path,
                        "$.config_status",
                        f"未知配置状态：{raw_status!r}",
                    )
                )
            else:
                if not status.is_runtime:
                    issues.append(
                        ValidationIssue(
                            path,
                            "$.config_status",
                            f"非运行配置状态不得加载：{status.value}",
                        )
                    )
    issues.extend(_validate_value(path, data))
    return issues


def validate_config_file(path: Path) -> list[ValidationIssue]:
    try:
        source = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        return [ValidationIssue(path, "", f"文件不是有效 UTF-8：{exc}")]
    except OSError as exc:
        return [ValidationIssue(path, "", f"无法读取文件：{exc}")]

    try:
        data = json.loads(source, parse_constant=_reject_non_finite_number)
    except _NonFiniteNumberError as exc:
        return [
            ValidationIssue(
                path,
                "",
                f"JSON 包含非标准数值：{exc.token}",
            )
        ]
    except json.JSONDecodeError as exc:
        return [
            ValidationIssue(
                path,
                f"line {exc.lineno}, column {exc.colno}",
                f"JSON 格式错误：{exc.msg}",
            )
        ]
    return _validate_document(path, data)


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
