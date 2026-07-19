"""运行配置读取与校验入口。"""

from furnace_winter.config.loader import (
    ConfigLoadError,
    LoadedConfig,
    load_config_file,
    load_config_tree,
)
from furnace_winter.config.status import ConfigStatus
from furnace_winter.config.survival import (
    FurnaceLevelRule,
    StartingPopulationRules,
    StartingResourceRules,
    SurvivalConfigError,
    SurvivalRules,
    load_survival_rules,
)
from furnace_winter.config.validator import (
    ValidationIssue,
    ValidationReport,
    validate_config_file,
    validate_config_tree,
)

__all__ = [
    "ConfigLoadError",
    "ConfigStatus",
    "FurnaceLevelRule",
    "LoadedConfig",
    "StartingPopulationRules",
    "StartingResourceRules",
    "SurvivalConfigError",
    "SurvivalRules",
    "ValidationIssue",
    "ValidationReport",
    "load_config_file",
    "load_config_tree",
    "load_survival_rules",
    "validate_config_file",
    "validate_config_tree",
]
