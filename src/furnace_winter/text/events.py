from __future__ import annotations

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import TextEntry, TextRegistry, TextVisibility


_SOURCE = (
    "docs/text-assets/第 5 轮：Event  Promise  OldCity  FixedArrival  "
    "FrostWarning  Achievement.md"
)

_RUNTIME_TEXT = {
    "event.children_request.title": "孩子们的请求",
    "event.children_request.body": (
        "几个孩子站在炉边，没有靠得太近。\n\n"
        "他们问执政官：\n\n"
        "我们今天要去哪儿？\n\n"
        "没人回答。\n"
        "因为城市还没决定，孩子在这里算未来，还是算劳动力。"
    ),
    "event.children_request.option_a": "承诺安置儿童",
    "event.children_request.option_b": "暂时维持现状",
    "event.children_request.option_c": "安排炉边杂务",
    "arrival.day6.title": "早期求生者",
    "arrival.day19.title": "中期工程残队",
    "arrival.day37.title": "后期难民潮",
    "arrival.option.accept_all": "全部接纳",
    "arrival.option.accept_partial": "部分接纳",
    "arrival.option.reject": "拒绝接纳",
    "arrival.work_assignment.notice": (
        "新增人口当天能够工作，但不会自动分配岗位。请手动调整工作分配。"
    ),
    "arrival.immediate_pressure.notice": (
        "新增人口已经进城，并立即计入住房、食物、医疗和疾病压力。"
    ),
    "event.seventh_frost_start.title": "第七霜落",
    "event.black_frost_echo.title": "黑霜回声",
    "event.black_frost_echo.body": (
        "夜里，炉城外传来一种很低的声音。\n\n"
        "不是风。\n也不是雪。\n\n"
        "像有什么东西正在很远的地方压过冻土，把世界一点点磨平。\n\n"
        "工程师说，黑霜的回声已经到了。\n真正的第七霜落，还在路上。"
    ),
    "event.black_frost_echo.option_a": "公开预警",
    "event.black_frost_echo.option_b": "只通知管理与工程人员",
    "event.black_frost_echo.option_c": "暂缓公布",
    "event.final_preparation_window.title": "最后的整备窗口",
    "event.final_preparation_window.body": (
        "炉城的晨钟敲了很久。\n\n"
        "没有人迟到。\n没有人说话。\n\n"
        "他们都看见了天边那道灰白色的墙。\n"
        "它还没有压下来，但已经挡住了太阳。"
    ),
    "event.final_preparation_window.option_a": "公开最后整备清单",
    "event.final_preparation_window.option_b": "只向管理层通报",
    "event.final_preparation_window.option_c": "压下恐慌，继续日常运转",
    "event.city_night_terror.title": "炉城夜惊",
    "event.city_night_terror.body": (
        "那一夜，没有人真正睡着。\n\n"
        "炉城外的雪声像兽群在低伏。\n有人把孩子抱得很紧。\n"
        "有人一遍遍数煤仓。\n有人问工程师：\n\n"
        "炉心还能撑几天？\n\n工程师没有回答。"
    ),
    "event.city_night_terror.option_a": "发布最终动员",
    "event.city_night_terror.option_b": "维持秩序，避免恐慌",
    "event.city_night_terror.option_c": "不再粉饰情况",
}


def build_event_text_registry() -> TextRegistry:
    """Register sealed player-visible event and fixed-arrival text."""

    registry = TextRegistry()
    for text_id, text in _RUNTIME_TEXT.items():
        registry.register(
            TextEntry(
                text_id=text_id,
                text=text,
                status=ConfigStatus.FINAL,
                visibility=TextVisibility.PLAYER_VISIBLE,
                source=_SOURCE,
            )
        )
    return registry
