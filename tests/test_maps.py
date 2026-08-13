from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from furnace_winter.config import (
    load_building_rules,
    load_map_rules,
    load_survival_rules,
    validate_config_tree,
)
from furnace_winter.gameplay import MapSystem, create_initial_survival_state
from furnace_winter.interface import GameSession
from furnace_winter.models import (
    CURRENT_SAVE_DATA_VERSION,
    SaveDataError,
    decode_game_state,
    encode_game_state,
)


class MapPatchTests(unittest.TestCase):
    PROJECT_ROOT = Path(__file__).resolve().parents[1]

    @classmethod
    def setUpClass(cls) -> None:
        cls.data_dir = cls.PROJECT_ROOT / "data"
        cls.survival_rules = load_survival_rules(
            cls.data_dir / "survival.json"
        )
        cls.building_rules = load_building_rules(
            cls.data_dir / "buildings.json"
        )
        cls.map_rules = load_map_rules(cls.data_dir / "maps.json")
        cls.system = MapSystem(cls.map_rules, cls.building_rules)

    def create_state(
        self,
        *,
        seed: int = 0,
        map_mode: str = "random",
        map_key: str | None = None,
    ):
        return create_initial_survival_state(
            self.survival_rules,
            self.building_rules,
            random_seed=seed,
            map_rules=self.map_rules,
            map_selection_mode=map_mode,
            map_key=map_key,
        )

    def test_sealed_map_templates_and_weights_are_loaded(self) -> None:
        self.assertEqual(
            dict(self.map_rules.random_integer_weights),
            {
                "rustbone_tundra": 33,
                "black_ash_lowland": 34,
                "twin_source_rift": 33,
            },
        )
        self.assertEqual(
            {
                key: (
                    rule.display_name_zh,
                    rule.difficulty_zh,
                    rule.large_coal_mine_points,
                    rule.large_steel_mine_points,
                )
                for key, rule in self.map_rules.templates.items()
            },
            {
                "rustbone_tundra": ("锈骨冻原", "偏难", 1, 2),
                "black_ash_lowland": ("黑烬洼地", "标准", 2, 1),
                "twin_source_rift": ("双源裂谷", "偏易", 2, 2),
            },
        )

    def test_map_config_and_building_links_are_strict(self) -> None:
        source = json.loads(
            (self.data_dir / "maps.json").read_text(encoding="utf-8")
        )
        invalid_documents = []
        invalid_weights = deepcopy(source)
        invalid_weights["selection"]["random_integer_weights"][
            "rustbone_tundra"
        ] = 32
        invalid_documents.append(invalid_weights)
        missing_template = deepcopy(source)
        missing_template["templates"].pop("twin_source_rift")
        invalid_documents.append(missing_template)

        for index, document in enumerate(invalid_documents):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "maps.json"
                path.write_text(
                    json.dumps(document, ensure_ascii=False),
                    encoding="utf-8",
                )
                with self.assertRaises(ValueError):
                    load_map_rules(path)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for path in self.data_dir.glob("*.json"):
                document = json.loads(path.read_text(encoding="utf-8"))
                if path.name == "buildings.json":
                    document["surface_resource_points"][
                        "surface-coal-1"
                    ]["resource_type"] = "wood"
                (root / path.name).write_text(
                    json.dumps(document, ensure_ascii=False),
                    encoding="utf-8",
                )
            report = validate_config_tree(root)

        self.assertFalse(report.is_valid)
        self.assertTrue(
            any(
                "地图与建筑跨配置校验失败" in issue.message
                for issue in report.issues
            )
        )

    def test_final_map_config_rejects_each_sealed_value_tamper(
        self,
    ) -> None:
        source = json.loads(
            (self.data_dir / "maps.json").read_text(encoding="utf-8")
        )

        def replace(
            path: tuple[str, ...],
            value,
        ):
            def mutate(document) -> None:
                target = document
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value

            return mutate

        mutations = [
            (
                "schema_version",
                replace(("schema_version",), 2),
            ),
            (
                "config_status",
                replace(("config_status",), "USER_OVERRIDE"),
            ),
            (
                "default_mode",
                replace(("selection", "default_mode"), "manual"),
            ),
            (
                "legacy_default_map_key",
                replace(
                    ("selection", "legacy_default_map_key"),
                    "twin_source_rift",
                ),
            ),
            (
                "weights_1_98_1",
                replace(
                    ("selection", "random_integer_weights"),
                    {
                        "rustbone_tundra": 1,
                        "black_ash_lowland": 98,
                        "twin_source_rift": 1,
                    },
                ),
            ),
            (
                "rustbone_weight",
                replace(
                    ("selection", "random_integer_weights"),
                    {
                        "rustbone_tundra": 34,
                        "black_ash_lowland": 33,
                        "twin_source_rift": 33,
                    },
                ),
            ),
            (
                "black_ash_weight",
                replace(
                    ("selection", "random_integer_weights"),
                    {
                        "rustbone_tundra": 32,
                        "black_ash_lowland": 35,
                        "twin_source_rift": 33,
                    },
                ),
            ),
            (
                "twin_source_weight",
                replace(
                    ("selection", "random_integer_weights"),
                    {
                        "rustbone_tundra": 33,
                        "black_ash_lowland": 33,
                        "twin_source_rift": 34,
                    },
                ),
            ),
        ]
        for key, value in (
            ("small_coal_piles", 5),
            ("small_wood_piles", 6),
            ("small_steel_piles", 4),
            ("initial_hunting_grounds", 2),
            ("total_hunting_grounds", 3),
            ("forest_zones", 3),
        ):
            mutations.append(
                (
                    f"shared_{key}",
                    replace(("shared", key), value),
                )
            )
        for map_key in (
            "rustbone_tundra",
            "black_ash_lowland",
            "twin_source_rift",
        ):
            template = source["templates"][map_key]
            mutations.extend(
                (
                    (
                        f"{map_key}_display_name",
                        replace(
                            ("templates", map_key, "display_name_zh"),
                            f"{template['display_name_zh']}改",
                        ),
                    ),
                    (
                        f"{map_key}_difficulty",
                        replace(
                            ("templates", map_key, "difficulty_zh"),
                            f"{template['difficulty_zh']}改",
                        ),
                    ),
                    (
                        f"{map_key}_large_coal",
                        replace(
                            (
                                "templates",
                                map_key,
                                "large_coal_mine_points",
                            ),
                            template["large_coal_mine_points"] + 1,
                        ),
                    ),
                    (
                        f"{map_key}_large_steel",
                        replace(
                            (
                                "templates",
                                map_key,
                                "large_steel_mine_points",
                            ),
                            template["large_steel_mine_points"] + 1,
                        ),
                    ),
                )
            )

        for label, mutate in mutations:
            with (
                self.subTest(label=label),
                tempfile.TemporaryDirectory() as temp_dir,
            ):
                document = deepcopy(source)
                mutate(document)
                path = Path(temp_dir) / "maps.json"
                path.write_text(
                    json.dumps(document, ensure_ascii=False),
                    encoding="utf-8",
                )

                with self.assertRaises(ValueError):
                    load_map_rules(path)
                self.assertFalse(validate_config_tree(path.parent).is_valid)

    def test_weight_field_order_does_not_change_new_or_saved_random_map(
        self,
    ) -> None:
        source = json.loads(
            (self.data_dir / "maps.json").read_text(encoding="utf-8")
        )
        weights = source["selection"]["random_integer_weights"]
        source["selection"]["random_integer_weights"] = {
            key: weights[key]
            for key in reversed(tuple(weights))
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "maps.json"
            path.write_text(
                json.dumps(source, ensure_ascii=False),
                encoding="utf-8",
            )
            reordered_rules = load_map_rules(path)

        original = self.create_state(seed=2)
        reordered = create_initial_survival_state(
            self.survival_rules,
            self.building_rules,
            random_seed=2,
            map_rules=reordered_rules,
        )
        self.assertEqual(original.map, reordered.map)
        self.assertEqual(original.random, reordered.random)
        self.assertEqual(original.map.map_key, "rustbone_tundra")

        restored = decode_game_state(encode_game_state(original))
        MapSystem(reordered_rules, self.building_rules).validate_state(
            restored
        )

    def test_random_selection_is_seeded_reproducible_and_uses_one_draw(
        self,
    ) -> None:
        expected = {
            0: "black_ash_lowland",
            2: "rustbone_tundra",
            4: "twin_source_rift",
        }
        for seed, map_key in expected.items():
            with self.subTest(seed=seed):
                first = self.create_state(seed=seed)
                second = self.create_state(seed=seed)
                self.assertEqual(first, second)
                self.assertEqual(first.map.map_key, map_key)
                self.assertEqual(first.map.selection_mode, "random")
                self.assertEqual(first.random.draws, 1)
                self.system.validate_state(first)

    def test_manual_selection_uses_no_random_draw_and_only_mines_differ(
        self,
    ) -> None:
        baseline = None
        for map_key in self.map_rules.templates:
            with self.subTest(map_key=map_key):
                state = self.create_state(
                    seed=41,
                    map_mode="manual",
                    map_key=map_key,
                )
                self.assertEqual(state.map.map_key, map_key)
                self.assertEqual(state.map.selection_mode, "manual")
                self.assertEqual(state.random.draws, 0)
                common = (
                    state.map.small_coal_piles,
                    state.map.small_wood_piles,
                    state.map.small_steel_piles,
                    state.map.initial_hunting_grounds,
                    state.map.total_hunting_grounds,
                    state.map.forest_zones,
                    state.population,
                    state.resources,
                    state.surface_resource_points,
                )
                if baseline is None:
                    baseline = common
                else:
                    self.assertEqual(common, baseline)
                self.system.validate_state(state)

    def test_selection_rejects_invalid_mode_key_combinations(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires map_key"):
            self.create_state(map_mode="manual")
        with self.assertRaisesRegex(ValueError, "cannot specify"):
            self.create_state(
                map_mode="random",
                map_key="black_ash_lowland",
            )
        with self.assertRaisesRegex(ValueError, "unknown map_key"):
            self.create_state(map_mode="manual", map_key="missing")
        with self.assertRaisesRegex(ValueError, "must be"):
            self.create_state(map_mode="surprise")

    def test_config_aware_validation_rejects_map_tampering(self) -> None:
        state = self.create_state(seed=2)
        mutations = (
            ("map key", lambda item: setattr(item.map, "map_key", "twin_source_rift")),
            (
                "display name",
                lambda item: setattr(item.map, "display_name_zh", "伪造地图"),
            ),
            (
                "large mine count",
                lambda item: setattr(item.map, "large_coal_mine_points", 99),
            ),
            (
                "surface point",
                lambda item: item.surface_resource_points.pop(
                    "surface-coal-1"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                tampered = deepcopy(state)
                mutate(tampered)
                with self.assertRaises(ValueError):
                    self.system.validate_state(tampered)

    def test_v12_migration_uses_explicit_legacy_standard_without_random_draw(
        self,
    ) -> None:
        state = self.create_state(
            seed=77,
            map_mode="manual",
            map_key="twin_source_rift",
        )
        legacy = encode_game_state(state)
        legacy["save_data_version"] = 12
        del legacy["final_frost"]["balance_profile_id"]
        legacy.pop("map")
        random_before = deepcopy(legacy["random"])

        migrated = decode_game_state(legacy)

        self.assertEqual(
            migrated.save_data_version, CURRENT_SAVE_DATA_VERSION
        )
        self.assertEqual(migrated.map.map_key, "black_ash_lowland")
        self.assertEqual(migrated.map.selection_mode, "legacy_default")
        self.assertEqual(encode_game_state(migrated)["random"], random_before)
        self.system.validate_state(migrated)

        smuggled = deepcopy(legacy)
        smuggled["map"] = encode_game_state(state)["map"]
        with self.assertRaisesRegex(
            SaveDataError, "pre-v13 save cannot contain non-default map"
        ):
            decode_game_state(smuggled)

    def test_session_exposes_map_rules_status_observation_and_round_trip(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "manual-map.json"
            session = GameSession.new(
                config_dir=self.data_dir,
                save_path=save_path,
                seed=91,
                map_mode="manual",
                map_key="rustbone_tundra",
            )
            self.assertEqual(
                session.status()["map"]["map_key"], "rustbone_tundra"
            )
            self.assertEqual(
                session.observe().map_view["large_mine_points"],
                {"coal": 1, "steel": 2},
            )
            self.assertEqual(
                session.rules_view("maps")["config_status"], "FINAL"
            )

            restored = GameSession.load(
                save_path, config_dir=self.data_dir
            )
            self.assertEqual(restored.state, session.state)
            self.assertEqual(
                restored.replay_document().initial_state["map"]["map_key"],
                "rustbone_tundra",
            )


if __name__ == "__main__":
    unittest.main()
