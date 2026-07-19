from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from furnace_winter.config import validate_config_tree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="furnace-winter",
        description="《炉心残冬》开发入口（Patch 000 骨架）",
    )
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="校验 data/ 下的 JSON 运行配置",
    )
    validate_parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("data"),
        help="配置目录，默认 data/",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "validate-config":
        parser.print_help()
        return 0

    report = validate_config_tree(args.path)
    if report.is_valid:
        print(f"配置校验通过：检查了 {report.files_checked} 个 JSON 文件。")
        return 0

    print("配置校验失败：")
    for issue in report.issues:
        print(f"- {issue}")
    return 1
