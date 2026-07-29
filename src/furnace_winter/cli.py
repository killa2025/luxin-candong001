from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from furnace_winter.config import (
    load_building_rules,
    load_event_rules,
    load_final_frost_rules,
    load_law_rules,
    load_oath_order_rules,
    load_survival_rules,
    load_technology_rules,
    validate_config_tree,
)
from furnace_winter.gameplay import (
    BuildingSystem,
    EndDayEngine,
    EndingReportSystem,
    EventSystem,
    FinalFrostSystem,
    LawSystem,
    OathOrderSystem,
    SurvivalSystem,
    TechnologySystem,
    create_initial_survival_state,
)
from furnace_winter.interface import GameSession, Observation
from furnace_winter.models import decode_game_state, dumps


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
        help="输出 Patch 007 事件、承诺与固定增员接口的机器可读开局状态",
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
        "--final-frost-config",
        type=Path,
        default=Path("data/final_frost.json"),
        help="Patch 009 final-frost and ending-score configuration",
    )
    state_parser.add_argument(
        "--oath-order-config",
        type=Path,
        default=Path("data/oath_order.json"),
        help="Patch 008 旧城派与誓言/铁腕规则配置",
    )
    state_parser.add_argument(
        "--technologies-config",
        type=Path,
        default=Path("data/technologies.json"),
        help="Patch 006 科技规则配置，默认 data/technologies.json",
    )
    report_parser = subparsers.add_parser(
        "report",
        help="输出存档中的 Patch 010 机器可读终局报告",
    )
    report_parser.add_argument(
        "save_path",
        type=Path,
        help="需要读取的 JSON 存档路径",
    )
    play_parser = subparsers.add_parser(
        "play",
        help="启动供沙盒 AI 使用的持久化 JSON Lines 游戏会话",
    )
    play_parser.add_argument(
        "save_path",
        type=Path,
        help="会话存档路径；不存在时自动建立新局",
    )
    play_parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="运行配置目录，默认 data/",
    )
    play_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="仅在新建存档时使用的统一随机种子",
    )
    play_parser.add_argument(
        "--new",
        action="store_true",
        help="明确建立新局；已有存档时默认拒绝覆盖",
    )
    play_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="与 --new 同用时允许覆盖已有存档",
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
        final_frost_rules = load_final_frost_rules(args.final_frost_config)
        oath_order_rules = load_oath_order_rules(args.oath_order_config)
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
        oath_order = OathOrderSystem(
            oath_order_rules,
            building_rules,
            rules,
            technology_rules,
        )
        final_frost = FinalFrostSystem(
            final_frost_rules,
            building_rules,
            rules,
            technology_rules,
        )
        ending_report = EndingReportSystem()
        events.initialize_day(state)
        command_specs = (
            EndDayEngine().command_specs()
            + survival.command_specs()
            + buildings.command_specs()
            + laws.command_specs()
            + technologies.command_specs()
            + events.command_specs()
            + oath_order.command_specs()
            + ending_report.command_specs()
        )
        print(
            dumps(
                Observation.from_state(
                    state,
                    command_specs,
                    event_views=events.active_event_views(state),
                    promise_views=events.active_promise_views(state),
                    old_city_view=oath_order.old_city_view(state),
                    oath_order_view=oath_order.route_view(state),
                    final_frost_view=final_frost.observe(state),
                    ending_report_view=ending_report.observe(state),
                )
            )
        )
        return 0

    if args.command == "report":
        document = json.loads(
            args.save_path.read_text(encoding="utf-8-sig")
        )
        state = decode_game_state(document)
        print(dumps(EndingReportSystem().observe(state)))
        return 0

    if args.command == "play":
        try:
            if args.new:
                session = GameSession.new(
                    config_dir=args.data_dir,
                    save_path=args.save_path,
                    seed=args.seed,
                    overwrite=args.overwrite,
                )
            else:
                session = GameSession.open(
                    args.save_path,
                    config_dir=args.data_dir,
                    seed=args.seed,
                )
        except Exception as exc:
            print(
                dumps(
                    {
                        "type": "error",
                        "code": "SESSION_START_FAILED",
                        "exception_type": type(exc).__name__,
                    }
                ),
                flush=True,
            )
            return 1

        print(
            dumps(
                {
                    "type": "observation",
                    "observation": session.observe(),
                    "status": session.status(),
                }
            ),
            flush=True,
        )
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                print(
                    dumps(
                        {
                            "type": "error",
                            "code": "INVALID_JSON",
                        }
                    ),
                    flush=True,
                )
                continue
            if not isinstance(payload, Mapping):
                print(
                    dumps(
                        {
                            "type": "error",
                            "code": "INVALID_ENVELOPE",
                        }
                    ),
                    flush=True,
                )
                continue
            envelope_type = payload.get("type", "command")
            try:
                if envelope_type == "observe":
                    response = {
                        "type": "observation",
                        "observation": session.observe(),
                        "status": session.status(),
                    }
                elif envelope_type == "rules":
                    response = {
                        "type": "rules",
                        "rules": session.rules_view(
                            str(payload.get("section", ""))
                        ),
                    }
                elif envelope_type == "replay":
                    response = {
                        "type": "replay",
                        "replay": session.replay_document(),
                    }
                elif envelope_type == "quit":
                    print(
                        dumps(
                            {
                                "type": "closed",
                                "status": session.status(),
                            }
                        ),
                        flush=True,
                    )
                    return 0
                elif envelope_type == "command":
                    request_payload = payload.get("request", payload)
                    if request_payload is payload:
                        request_payload = {
                            key: value
                            for key, value in payload.items()
                            if key != "type"
                        }
                    response = {
                        "type": "execution",
                        "execution": session.execute_payload(request_payload),
                    }
                else:
                    response = {
                        "type": "error",
                        "code": "UNKNOWN_ENVELOPE_TYPE",
                    }
            except Exception as exc:
                response = {
                    "type": "error",
                    "code": "SESSION_REQUEST_FAILED",
                    "exception_type": type(exc).__name__,
                }
            print(dumps(response), flush=True)
        return 0

    parser.print_help()
    return 0
