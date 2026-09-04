from __future__ import annotations

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import TextEntry, TextRegistry, TextVisibility


_SOURCE = (
    "docs/text-assets/第 5 轮：Event  Promise  OldCity  FixedArrival  "
    "FrostWarning  Achievement.md"
)
_PATCH031_SOURCE = (
    "docs/handoff/PATCH-031：事件缺失正文收口实现记录.md"
)
_PATCH031_TEXT_IDS = {
    "event.long_shift_collapse.body",
    "event.overtime_empty_post.body",
    "arrival.day6.body",
    "arrival.day19.body",
    "arrival.day37.body",
    "event.seventh_frost_start.body",
}
_PATCH032_SOURCE = (
    "docs/handoff/PATCH-032：旧城派阶段事件正文收口实现记录.md"
)
_PATCH032_TEXT_IDS = {
    "old_city.event.southern_letter.body",
    "old_city.event.hidden_rumors.body",
    "old_city.event.public_gathering.body",
    "old_city.event.exodus_countdown.body",
}
_PATCH033_SOURCE = (
    "docs/handoff/PATCH-033：事件与承诺反馈文案收口实现记录.md"
)
_PATCH047_SOURCE = "docs/handoff/PATCH-047：煤务统计与终局解释修复实现记录.md"
_PATCH033_TEXT_IDS = {
    "event.option.unavailable.feedback",
    "promise.same_type.active",
    "promise.success.title",
    "promise.failure.title",
}

_RUNTIME_TEXT = {
    "event.option.unavailable.feedback": (
        "这个选项当前不可用。请查看返回的具体原因与所需条件。"
    ),
    "promise.same_type.active": (
        "同类型承诺仍在履行中。在它完成或失败以前，不能再次作出相同承诺。"
    ),
    "promise.success.title": "承诺兑现",
    "promise.failure.title": "承诺落空",
    "event.empty_pot.title": "空锅请愿",
    "event.empty_pot.body": (
        "食堂外有人举起空碗。\n\n"
        "他们没有闹事，只是站在那里。\n"
        "碗底被刮得很干净，像一圈冻住的月亮。\n\n"
        "有人说：我们不是要更多，只是想知道明天还有没有。"
    ),
    "event.empty_pot.option_a": "承诺补足口粮",
    "event.empty_pot.option_b": "维持当前配给",
    "event.empty_pot.option_c": "调整配给",
    "event.raw_food_dispute.title": "生食争议",
    "event.raw_food_dispute.body": (
        "有人在炉边啃半冻的生肉。\n\n"
        "孩子看着那块肉，没有说话。\n"
        "大人也没有。\n\n"
        "第二天，医疗站多了几张发冷的脸。"
    ),
    "event.raw_food_dispute.option_a": "承诺恢复熟食供应",
    "event.raw_food_dispute.option_b": "暂时允许继续食用生食",
    "event.raw_food_dispute.option_c": "优先供应儿童熟食",
    "event.medical_beds_emergency.title": "病床告急",
    "event.medical_beds_emergency.body": (
        "医疗站门口排着人。\n\n"
        "有人坐在雪里，有人靠着墙睡着。\n"
        "医生没有抬头，只说了一句：\n\n"
        "下一个床位空出来之前，别再有人倒下了。"
    ),
    "event.medical_beds_emergency.option_a": "承诺扩容医疗",
    "event.medical_beds_emergency.option_b": "临时腾挪床位",
    "event.medical_beds_emergency.option_c": "维持现状",
    "event.severe_case_backlog.title": "重症积压",
    "event.severe_case_backlog.body": (
        "医疗站里安静得不正常。\n\n"
        "重症病人不再呻吟。\n"
        "他们只是看着炉光，好像那是某种很远的东西。\n\n"
        "医生说：我们还能救一些人。\n"
        "但不是所有人。"
    ),
    "event.severe_case_backlog.option_a": "投入额外医疗配给",
    "event.severe_case_backlog.option_b": "承诺扩大重症收治能力",
    "event.severe_case_backlog.option_c": "接受现状",
    "event.first_body.title": "第一具遗体",
    "event.first_body.body": (
        "他们把那个人抬到炉边时，雪还粘在他的袖口上。\n\n"
        "没人知道该把他放在哪里。\n"
        "也没人愿意第一个说：\n\n"
        "他已经不需要床位了。"
    ),
    "event.first_body.option_a": "公开悼念",
    "event.first_body.option_b": "低调处理",
    "event.first_body.option_c": "暂时搁置",
    "event.bodies_under_snow.title": "雪下尸列",
    "event.bodies_under_snow.body": (
        "雪把遗体盖住了一半。\n\n"
        "这本来让他们看起来安静些。\n"
        "但风一吹，露出来的手指又提醒所有人：\n\n"
        "他们还在这里。"
    ),
    "event.bodies_under_snow.option_a": "承诺处理遗体",
    "event.bodies_under_snow.option_b": "举行临时悼念",
    "event.bodies_under_snow.option_c": "继续搁置",
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
    "event.red_frozen_hands.title": "冻红的手",
    "event.red_frozen_hands.body": (
        "一个孩子把手藏在袖子里。\n\n"
        "医生让他伸出来。\n"
        "他不肯。\n\n"
        "后来人们才看见，那双手已经冻得发红，"
        "指节肿得像小块木炭。"
    ),
    "event.red_frozen_hands.option_a": "暂停儿童高风险劳动",
    "event.red_frozen_hands.option_b": "提供额外防寒照料",
    "event.red_frozen_hands.option_c": "继续维持安排",
    "event.long_shift_collapse.title": "长班后的倒下",
    "event.long_shift_collapse.body": (
        "长班还没有结束，就有人在岗位旁倒了下去。\n"
        "没有事故，也没有巨响。只是身体终于比命令更早承认，它已经撑不住了。\n"
        "其他人停了一会儿，又重新回到工作里。\n"
        "炉城缺的从来不只是一双手。\n"
        "更缺的是允许那双手停下来的余地。"
    ),
    "event.long_shift_collapse.option_a": "暂停长班一天",
    "event.long_shift_collapse.option_b": "提供熟食补偿",
    "event.long_shift_collapse.option_c": "继续长班",
    "event.overtime_empty_post.title": "加班后的空位",
    "event.overtime_empty_post.body": (
        "加班已经不是第一次。\n"
        "今天点名时，一个岗位没有等到应该站在那里的人。\n"
        "炉城仍然可以把别人调过去，把缺口重新填满。\n"
        "可岗位可以补，人却不能像名册上的数字一样无限往前挪。\n"
        "当每一个空位都需要另一个更疲惫的人顶上去时——\n"
        "迟早还会再空一个。"
    ),
    "event.overtime_empty_post.option_a": "承诺补足人手或降低过劳压力",
    "event.overtime_empty_post.option_b": "提供熟食补偿",
    "event.overtime_empty_post.option_c": "继续维持安排",
    "event.coal_bottom.title": "煤仓见底",
    "event.coal_bottom.body": (
        "煤仓底部露出来了。\n\n"
        "铲子碰到木板时，声音比风还空。"
    ),
    "event.coal_bottom.option_a": "承诺补足煤炭储备",
    "event.coal_bottom.option_b": "调整炉心消耗",
    "event.coal_bottom.option_c": "维持现状",
    "event.furnace_redline.title": "炉心红线",
    "event.furnace_redline.warning": (
        "炉心压力已达到极限。\n"
        "这是最后一次手动关闭过载的机会。\n"
        "若继续维持过载，下一次日结可能导致炉心崩毁。"
    ),
    "event.furnace_redline.option_a": "立即关闭过载",
    "event.furnace_redline.option_b": "承诺完成炉心减压方案",
    "event.furnace_redline.option_c": "维持过载 / 暂不处理",
    "event.cold_house_night.title": "寒屋之夜",
    "event.cold_house_night.body": (
        "夜里，有人把炉灰抹在墙缝上。\n\n"
        "没有用。\n\n"
        "风还是从缝里钻进来，摸过孩子的脚踝，"
        "摸过老人的膝盖，最后停在每个人的肺里。"
    ),
    "event.cold_house_night.option_a": "承诺补足住房 / 保温",
    "event.cold_house_night.option_b": "提高炉心档位",
    "event.cold_house_night.option_c": "维持现状",
    "event.trust_crack.title": "信任裂缝",
    "event.trust_crack.body": (
        "人们还在工作。\n\n"
        "他们仍然走向矿井、食堂、医疗站和炉边。\n"
        "但他们不再看执政官的眼睛。\n\n"
        "城市没有立刻崩塌。\n"
        "只是有一根东西断了。"
    ),
    "event.trust_crack.option_a": "承诺恢复信任",
    "event.trust_crack.option_b": "发布安抚公告 / 公开说明",
    "event.trust_crack.option_c": "维持现状",
    "event.city_unrest.title": "炉城骚动",
    "event.city_unrest.body": (
        "有人在夜里喊了一声。\n\n"
        "很快，更多人醒了。\n"
        "他们不知道自己要去哪里，也不知道自己要找谁。\n\n"
        "恐惧在炉城里跑得比人更快。"
    ),
    "event.city_unrest.option_a": "承诺降低恐慌",
    "event.city_unrest.option_b": "组织安抚 / 巡查",
    "event.city_unrest.option_c": "维持现状",
    "old_city.event.southern_letter.title": "南方来信",
    "old_city.event.southern_letter.body": (
        "今天，一封从南方辗转送来的信进了炉城。\n"
        "信里的消息并不完整，却提到更远的地方或许仍有人活着，也许还有能够落脚的去处。\n"
        "没人知道这封信经过了多久，也没人能确认里面的话还剩几分真实。\n"
        "可只要“城外也许还有路”这句话被人看见，\n"
        "炉城就已经不再是唯一的答案。"
    ),
    "old_city.event.southern_letter.option_a": "公布来信",
    "old_city.event.southern_letter.option_b": "压下来信",
    "old_city.event.hidden_rumors.title": "暗中传言",
    "old_city.event.hidden_rumors.body": (
        "最近，关于离开炉城的消息开始在私下流传。\n"
        "有人说南边还有聚居地，有人说旧路并没有完全断掉，也有人只是反复问同一句话：\n"
        "这里真的是最后一个还能活下去的地方吗？\n"
        "这些话还没有被公开喊出来。\n"
        "它们只是出现在排队、换班和熄灯以后，\n"
        "越来越多人听见，也越来越少人愿意承认自己听见过。"
    ),
    "old_city.event.hidden_rumors.option_a": "公开解释",
    "old_city.event.hidden_rumors.option_b": "暂不处理",
    "old_city.event.public_gathering.title": "公开集结",
    "old_city.event.public_gathering.body": (
        "原本藏在低声交谈里的怀疑，今天第一次聚到了明面上。\n"
        "越来越多人停在公共区域，没有散去。\n"
        "他们谈论城外的去处，谈论炉城还能撑多久，也要求得到一个足以让人继续留下的答案。\n"
        "这还不是一场出走。\n"
        "但已经不再只是传言。\n"
        "当怀疑开始站在人群中央，\n"
        "执政官就不能再假装它只存在于角落里。"
    ),
    "old_city.event.public_gathering.option_a": "公开说明",
    "old_city.event.public_gathering.option_b": "加强巡查",
    "old_city.event.public_gathering.option_c": "暂不处理",
    "old_city.event.exodus_countdown.title": "离城倒计时",
    "old_city.event.exodus_countdown.body": (
        "旧城派的人数还在上升。\n"
        "如今，已经有人开始整理能够带走的东西，询问城门、路线和外面的天气。\n"
        "他们还没有真正离开。\n"
        "可“要不要走”正在变成“什么时候走”。\n"
        "炉城仍有时间。\n"
        "只是已经没人能再把这件事当成一句随时会散掉的抱怨。\n"
        "当有人开始为离开做准备时，\n"
        "留下本身，也开始需要一个理由。"
    ),
    "old_city.event.exodus_countdown.option_a": "承诺压低旧城派人数",
    "old_city.event.exodus_countdown.option_b": "暂不阻拦",
    "old_city.event.exodus_countdown.option_c": "争取最后时间",
    "arrival.day6.title": "早期求生者",
    "arrival.day6.body": (
        "雪线外出现了一批求生者。\n"
        "他们没有带来足以改变炉城命运的东西，只带来了还能劳动的身体，以及身后已经无法回去的路。\n"
        "城里的人看着他们。\n"
        "多几双手，也意味着多几张嘴。\n"
        "寒冬第一次逼你承认：\n"
        "救下一个人和养活一个人，从来不是同一道题。"
    ),
    "arrival.day19.title": "中期工程残队",
    "arrival.day19.body": (
        "一支残余工程队抵达了炉城。\n"
        "他们知道怎样修东西，也知道一座设施在彻底坏掉以前，会先发出什么声音。\n"
        "这本该算是好消息。\n"
        "可炉城现在最不缺的，正是需要修补的东西。\n"
        "新的工程人手走进城门时，没有人问他们还能建造什么。\n"
        "人们先问的是——\n"
        "还有什么来得及不让它坏掉。"
    ),
    "arrival.day37.title": "后期难民潮",
    "arrival.day37.body": (
        "黑霜之后，又有人出现在城外。\n"
        "这一次不是零散的求生者。\n"
        "越来越多的人挤在炉城能够看见的地方，等待一扇门决定他们接下来还能不能活。\n"
        "城里的食物、床位和燃料不会因为同情而变多。\n"
        "可把门关上以后，\n"
        "风雪也不会替你忘记门外还有人。"
    ),
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
    "event.seventh_frost_start.option_a": "守住炉城。",
    "event.seventh_frost_start.body": (
        "第七霜落来了。\n"
        "从今天起，城外不再是可以指望的退路，炉心、食物、医疗和住房都会被压到最后的余量。\n"
        "之前所有被拖延的问题，现在都要一起结账。\n"
        "炉城已经没有多少东西可以再失去。\n"
        "接下来的七天，只会回答一个问题：\n"
        "你此前选择保住的一切，\n"
        "究竟够不够撑到风停。"
    ),
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
                source=(
                    _PATCH047_SOURCE
                    if text_id == "event.seventh_frost_start.option_a"
                    else _PATCH031_SOURCE
                    if text_id in _PATCH031_TEXT_IDS
                    else _PATCH032_SOURCE
                    if text_id in _PATCH032_TEXT_IDS
                    else _PATCH033_SOURCE
                    if text_id in _PATCH033_TEXT_IDS
                    else _SOURCE
                ),
            )
        )
    return registry
