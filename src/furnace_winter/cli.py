from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from furnace_winter.config import (
    load_building_rules,
    load_event_rules,
    load_law_rules,
    load_survival_rules,
    load_technology_rules,
    validate_config_tree,
)
from furnace_winter.gameplay import (
    BuildingSystem,
    EndDayEngine,
    EventSystem,
    LawSystem,
    SurvivalSystem,
    TechnologySystem,
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
        help="输出 Patch 006 炉律、科技研究与过载闭环的机器可读开局状态",
    )
    state_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="统一随机种子，默认 0",
    )
    state_parser.add_argument(
        "--buildings-config",
        type=Path,
        default=Path("data/buildings.json"),
        help="Patch 004 建筑规则配置，默认 data/buildings.json",
    )
    state_parser.add_argument(
        "--config",
        type=Path,
        default=Path("data/survival.json"),
        help="Patch 003 生存规则配置，默认 data/survival.json",
    )
    state_parser.add_argument(
        "--laws-config",
        type=Path,
        default=Path("data/laws.json"),
        help="Patch 005 炉律规则配置，默认 data/laws.json",
    )
    state_parser.add_argument(
        "--events-config",
        type=Path,
        default=Path("data/events.json"),
        help="Patch 007 事件、承诺与固定增员规则配置，默认 data/events.json",
    )
    state_parser.add_argument(
        "--technologies-config",
        type=Path,
        default=Path("data/technologies.json"),
        help="Patch 006 科技规则配置，默认 data/technologies.json",
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
        building_rules = load_building_rules(args.buildings_config)
        law_rules = load_law_rules(args.laws_config)
        technology_rules = load_technology_rules(args.technologies_config)
        event_rules = load_event_rules(args.events_config)
        state = create_initial_survival_state(
            rules, building_rules, random_seed=args.seed
        )
        survival = SurvivalSystem(rules, building_rules, technology_rules)
        buildings = BuildingSystem(building_rules, rules, technology_rules)
        laws = LawSystem(law_rules, building_rules, rules, technology_rules)
        technologies = TechnologySystem(
            technology_rules,
            building_rules,
            rules,
            law_rules,
        )
        events = EventSystem(
            event_rules,
            building_rules,
            rules,
            technology_rules,
        )
        events.initialize_day(state)
        command_specs = (
            EndDayEngine().command_specs()
            + survival.command_specs()
            + buildings.command_specs()
            + laws.command_specs()
            + technologies.command_specs()
            + events.command_specs()
        )
        print(dumps(Observation.from_state(state, command_specs)))
        return 0

    parser.print_help()
    return 0
