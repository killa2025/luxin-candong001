from __future__ import annotations

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import TextEntry, TextRegistry, TextVisibility


PATCH039_SOURCE = "docs/handoff/PATCH-039：科技说明与延后研究门禁实现记录.md"

UNAVAILABLE_RESEARCH_TEXT = "该研究目前尚无法投入实际应用。"

TECHNOLOGY_DESCRIPTIONS = {
    "tech_drawing_board": (
        "把零散草图整理成可复用的工程图，开放 T1 科技研究资格；"
        "不会自动完成任何 T1 科技。"
    ),
    "tech_drafting_instrument": (
        "让更复杂的结构能够被准确绘制和复核，开放 T2 科技研究资格；"
        "不会自动完成任何 T2 科技。"
    ),
    "tech_mechanical_calculator": (
        "用齿轮替代一部分反复验算，开放 T3 科技研究资格；"
        "不会自动完成任何 T3 科技。"
    ),
    "tech_difference_engine": (
        "让工程师能够处理更庞大的计算与设计，开放 T4 科技研究资格；"
        "不会自动完成任何 T4 科技。"
    ),
    "tech_automatic_forming_machine": (
        "将高精度零件的制造从手工误差中解放出来，开放 T5 科技研究资格；"
        "不会自动完成任何 T5 科技。"
    ),
    "tech_furnace_coal_saving_1": (
        "重整送煤与风门，降低炉心各档的基础煤耗；"
        "不减少 heat 或过载的额外煤耗。"
    ),
    "tech_building_insulation_1": (
        "为关键与工作建筑增加第一层保温，提高其有效温度；"
        "不赋予 heat 权限，也不作用于住宅。"
    ),
    "tech_furnace_power_stability_1": (
        "建立炉心高功率运行的稳定基础，并开放后续过载调校研究；"
        "本身不提供独立运行加成。"
    ),
    "tech_emergency_heating_device": (
        "改良现有应急加热装置，提高 heat 的加热效果；"
        "不会解锁 heat，也不会扩大可加热建筑范围。"
    ),
    "tech_furnace_coal_saving_2": (
        "继续压缩炉心的无效损耗，进一步降低各档基础煤耗；"
        "不减少 heat 或过载的额外煤耗。"
    ),
    "tech_building_insulation_2": (
        "将关键与工作建筑强化到更高保温等级；"
        "该效果取代建筑保温 I 而非叠加，不赋予 heat 权限，也不作用于住宅。"
    ),
    "tech_overload_tuning": (
        "解锁过载 1，使运行中的炉心能够以额外煤耗和压力增长换取更多热量；"
        "研究完成后不会自动开启过载。"
    ),
    "tech_overload_stability": (
        "解锁过载 2，并降低过载运行时的压力增长；"
        "研究完成后不会自动开启或提升过载。"
    ),
    "tech_final_furnace_stability": (
        "在第七霜落期间强化运行中的炉心，提高供暖并进一步抑制过载压力增长。"
    ),
    "tech_wood_processing_1": (
        "解锁伐木场建造。伐木场仍需逐座建造并绑定森林区，"
        "研究本身不会生成木材或自动建造建筑。"
    ),
    "tech_coal_seam_support": (
        "解锁小型采煤机建造。小型采煤机仍需逐座建造，"
        "不绑定大型煤矿点，也不消耗地表煤堆。"
    ),
    "tech_steel_screening": (
        "解锁小型采钢机建造。小型采钢机仍需逐座建造，"
        "不绑定大型钢铁矿点，也不消耗地表钢铁堆。"
    ),
    "tech_wood_processing_2": (
        "改良伐木场的加工流程，提高伐木场产出；不强化森林区本身。"
    ),
    "tech_small_coal_mining_improvement": "改良小型采煤机，提高其煤炭产出。",
    "tech_small_steel_mining_improvement": "改良小型采钢机，提高其钢材产出。",
    "tech_storage_expansion": (
        "提高每座小仓库提供的仓储容量，既有和以后建造的小仓库均适用；"
        "不会自动建造仓库。"
    ),
    "tech_housing_insulation_1": (
        "为基础、改良和高级住宅增加保温，提高住宅有效温度；"
        "不会让住宅获得 heat 权限。"
    ),
    "tech_canteen_process_improvement": (
        "改良食堂流程，提高每日生食处理上限；"
        "生食转化为熟食的基础比例不变。"
    ),
    "tech_medical_tools_improvement": (
        "改良医疗站使用的工具，提高医疗站容量；不改变医院容量。"
    ),
    "tech_greenhouse_cultivation": (
        "解锁温室建造。温室仍需逐座建造并生产生食，"
        "生食仍要经过食堂加工才能成为熟食。"
    ),
    "tech_medical_building_insulation": (
        "为当前可建的医疗站与医院增加保温，提高其有效温度；"
        "不会赋予新的治疗能力。"
    ),
    "tech_improved_housing_standard": (
        "解锁基础住宅到改良住宅的逐座升级，提高升级后住宅的容量；"
        "研究不会自动升级任何住宅。"
    ),
    "tech_hospital_standardization": (
        "解锁医院建造资格；正式建造医院还需要签署基础医疗法，"
        "研究本身不会自动建造医院。"
    ),
    "tech_greenhouse_improvement": (
        "解锁温室到改良温室的逐座升级，提高升级后温室的产出；"
        "研究不会自动升级任何温室。"
    ),
    "tech_advanced_housing_standard": (
        "解锁改良住宅到高级住宅的逐座升级，提高升级后住宅的容量；"
        "研究不会自动升级任何住宅。"
    ),
    "tech_scattered_gathering_tools": UNAVAILABLE_RESEARCH_TEXT,
    "tech_sheltered_gathering_shed_improvement": UNAVAILABLE_RESEARCH_TEXT,
    "tech_deep_well_mine_frame": UNAVAILABLE_RESEARCH_TEXT,
    "tech_deep_coal_seam_extraction": UNAVAILABLE_RESEARCH_TEXT,
    "tech_deep_steel_seam_extraction": UNAVAILABLE_RESEARCH_TEXT,
    "tech_hunting_equipment": UNAVAILABLE_RESEARCH_TEXT,
    "tech_field_cold_weather_equipment": UNAVAILABLE_RESEARCH_TEXT,
}


def technology_description_text_id(tech_id: str) -> str:
    if not tech_id.startswith("tech_"):
        raise ValueError("technology id must start with tech_")
    return f"tech.{tech_id.removeprefix('tech_')}.desc"


def build_technology_text_registry() -> TextRegistry:
    registry = TextRegistry()
    for tech_id, text in TECHNOLOGY_DESCRIPTIONS.items():
        registry.register(
            TextEntry(
                text_id=technology_description_text_id(tech_id),
                text=text,
                status=ConfigStatus.USER_OVERRIDE,
                visibility=TextVisibility.PLAYER_VISIBLE,
                source=PATCH039_SOURCE,
            )
        )
    return registry
