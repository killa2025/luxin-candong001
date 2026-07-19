from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from furnace_winter.config import load_survival_rules, validate_config_tree
from furnace_winter.gameplay import (
    EndDayEngine,
    SurvivalSystem,
    create_initial_survival_state,
)
from furnace_winter.interface import Observation
from furnace_winter.models import dumps


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="furnace-winter",
        description="《炉心残冬》机器接口入口",
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

    state_parser = subparsers.add_parser(
        "state",
        help="输出 Patch 003 封存开局的机器可读状态",
    )
    state_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="统一随机种子，默认 0",
    )
    state_parser.add_argument(
        "--config",
        type=Path,
        default=Path("data/survival.json"),
        help="Patch 003 生存规则配置，默认 data/survival.json",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-config":
        report = validate_config_tree(args.path)
        if report.is_valid:
            print(f"配置校验通过：检查了 {report.files_checked} 个 JSON 文件。")
            return 0

        print("配置校验失败：")
        for issue in report.issues:
            print(f"- {issue}")
        return 1

    if args.command == "state":
        rules = load_survival_rules(args.config)
        state = create_initial_survival_state(rules, random_seed=args.seed)
        survival = SurvivalSystem(rules)
        command_specs = EndDayEngine().command_specs() + survival.command_specs()
        print(dumps(Observation.from_state(state, command_specs)))
        return 0

    parser.print_help()
    return 0
