from __future__ import annotations

from furnace_winter.config import ConfigStatus
from furnace_winter.text.registry import (
    PendingEntry,
    PendingRegistry,
    TextEntry,
    TextRegistry,
    TextVisibility,
)


_SOURCE = (
    "docs/text-assets/第 6 轮：FrostFinal  Ending  HardFail  "
    "EndingReport  EndingTag  Interrogation.md"
)

_RUNTIME_TEXT = {
    "ending.title.hard_fail": "炉城终止",
    "ending.title.high_victory": "炉城存续",
    "ending.title.standard_victory": "炉城越冬",
    "ending.title.bitter_victory": "炉城残胜",
    "ending.title.collapse_survival": "崩坏幸存",
    "ending.title.ember_survival": "残火未灭",
    "ending.title.player_ended": "执政官终止执政",
    "ending.hard_fail.population_zero.title": "炉城终止",
    "ending.hard_fail.core_collapse.title": "炉心崩毁",
    "ending.hard_fail.trust_exile.title": "执政官被流放",
    "ending.hard_fail.panic_expelled.title": "执政官被驱逐",
    "ending.hard_fail.population_zero.reason": (
        "炉城最后一次点名时，没有人回答。"
    ),
    "ending.hard_fail.core_collapse.reason": (
        "炉心越过红线后，再也没有回到执政官的命令里。"
    ),
    "ending.hard_fail.trust_exile.reason": (
        "居民不再相信你有资格继续带领他们。"
    ),
    "ending.hard_fail.panic_expelled.reason": (
        "居民害怕你，胜过害怕门外的风雪。"
    ),
    "ending.player_ended.status": "本局由执政官亲手封存。",
    "ending.player_ended.closing": (
        "炉城档案封存。\n\n"
        "不是因为所有问题都有了答案。\n"
        "而是因为执政官决定，不再继续追问。"
    ),
    "ending.report.opening": "你带领 {start_population} 个人走入寒冬。",
    "ending.report.frostfall_deaths": (
        "最后七天里，第七霜落又带走了 {frostfall_deaths} 个"
        "再过几天就能见到曙光的人。"
    ),
    "ending.report.death_record.none": (
        "没有任何人被霜落吞噬，你做得很好，执政官。"
    ),
    "ending.report.death_record.cemetery": (
        "{total_deaths} 人没能走到最后。你为他们留下了墓园，"
        "那些名字化成了一个个墓碑被纪念。"
    ),
    "ending.report.death_record.cold_pit": (
        "{total_deaths} 人没能走到最后。他们被安置在冷藏坑的"
        "冰冷秩序里，等待炉城决定他们还有什么价值。"
    ),
    "ending.report.death_record.unhandled": (
        "{total_deaths} 人没能走到最后。档案封存时，"
        "{unhandled_bodies} 具遗体掩埋进风雪里。"
    ),
    "ending.report.death_record.ember_roster": (
        "{total_deaths} 人没能走到最后。余烬名册记下了他们的名字，"
        "让死者没有只成为冰冷的数字。"
    ),
    "ending.trace.child_labor": (
        "你签署了儿童辅工。孩子们用细嫩的手搬运木料、整理仓库，"
        "甚至在最冷的日子里跟着成年人走近风雪。炉城因此多撑住了"
        "一些时刻，而这些时刻会永远记得他们的年纪。"
    ),
    "ending.trace.cemetery": (
        "你为死者留下了墓园。那些名字没有只停在数字里，人们仍能"
        "在风雪间找到一处地方，承认他们曾经活过。"
    ),
    "ending.trace.cold_pit": (
        "你修建了冷藏坑。死者没有立刻离开炉城，他们被安置在冰冷"
        "的秩序里，等待城市决定如何继续面对他们。"
    ),
    "ending.trace.entertainment": (
        "你给炉城留下了喘息的地方。有人在小酒馆、火盆或赌桌旁"
        "短暂忘记寒冷；只是忘记不是解决，笑声也不能替炉心添煤。"
    ),
    "ending.trace.oath_route": (
        "你让炉城用誓言、悼亡、共食和名册维系彼此。它们不能让煤"
        "变多，也不能让死人回来，却让一些人在最冷的时候仍愿意留下。"
    ),
    "ending.trace.iron_route": (
        "你让炉城用巡查、点名、公告和留置维持秩序。它们不能让恐惧"
        "消失，却让恐惧学会排队，学会在命令前暂时低头。"
    ),
    "ending.trace.old_city": (
        "有人曾相信炉城之外还有另一条路。有人留下，有人离开，也有"
        "人只是把怀疑压回心里，继续围着炉心等待天亮。"
    ),
}

_TEXT_POOLS = {
    "ending.high_victory.body": (
        "第七霜落结束了。\n\n炉心仍在燃烧。\n食堂重新排起队。\n"
        "医疗站的灯没有熄。\n清晨点名时，大多数名字仍有人回答。\n\n"
        "这是一场少见的胜利。\n\n只是还有人记得，最初那些在雪地里"
        "冻硬的身躯。\n他们没有走到最终。\n却把空出来的位置，留给了后来的人。",
        "风雪退去时，炉城没有欢呼。\n\n人们只是走出门，确认烟囱还在，"
        "名册还在，孩子还在。\n有人把冻硬的门闩重新推开。\n有人开始计算"
        "下一顿饭。\n\n胜利没有声音。\n它只是让城市还能继续做明天的事。",
        "第七霜落没能把炉城压碎。\n\n煤仓没有彻底见底。\n病床没有完全"
        "溢出。\n炉心没有越线。\n大多数人仍在自己的床上醒来。\n\n这已经"
        "足够接近胜利。\n\n只是胜利也有背面。\n背面写着那些早在第七霜落"
        "之前，就倒在路上、病床上、雪地里的人。",
    ),
    "ending.standard_victory.body": (
        "第七霜落结束了。\n\n炉心还在烧。\n城市还在运转。\n有人死去，"
        "有人病倒，有人再也不能回到岗位上。\n\n炉城没有散。\n\n只是越过"
        "寒冬的人，必须从明天开始，和那些空床一起生活。",
        "最后一夜过去时，炉心旁仍有人值守。\n\n煤仓不算充足。\n食堂不算"
        "安稳。\n医疗站也不再像从前那样干净。\n\n可城市还在。\n\n这句话"
        "很沉。\n沉到足够压住欢呼。",
        "第七霜落没有给出宽恕。\n它只给出结果。\n\n炉城活下来了。\n\n"
        "执政官的命令、居民的忍耐、炉心里的煤，共同把这座城推过了"
        "第 55 天。\n\n推过去之后，人们才发现，自己仍然站在寒冬里。",
    ),
    "ending.bitter_victory.body": (
        "第七霜落结束了。\n\n炉心仍在燃烧。\n只是围在炉心旁的人少了"
        "很多。\n\n名册被翻到最后一页。\n活着的人没有欢呼。\n\n他们只是"
        "看着空出来的床位，等执政官宣布下一条命令。",
        "城市活下来了。\n\n这句话是真的。\n但它太轻，压不住雪下那些"
        "名字。\n\n炉城越过了第七霜落。\n代价已经写进每一间空屋。",
        "第七霜落没有杀死炉城。\n\n它只是拿走了太多东西。\n健康的人。\n"
        "相信的人。\n敢大声说话的人。\n\n炉心还在烧。\n可炉城的影子比"
        "从前短了。",
        "城市活下来了。",
    ),
    "ending.collapse_survival.body": (
        "第七霜落结束了。\n\n炉城没有死。\n这句话必须说得很小声。\n\n"
        "炉心还在烧。\n但它烧着的，不再像一座完整的城市。",
        "食堂还能排队。\n只是队伍里少了太多熟悉的脸。\n\n医疗站还开着。\n"
        "只是里面的人不再相信所有人都能轮到床位。",
        "命令仍能传下去。\n只是每一道命令，都要越过恐惧、饥饿、疲惫"
        "和沉默。\n\n炉城活过了第七霜落。\n但它不是胜利地站在那里。\n\n"
        "它是跪着，靠在炉心旁，勉强没有倒下。\n\n风雪没有彻底拿走它。\n"
        "可风雪也没有把它完整地还回来。",
    ),
    "ending.ember_survival.body": (
        "第七霜落结束了。\n\n炉心还剩一点火。\n\n那点火不够温暖一座城。\n"
        "只够证明炉城还没有完全死去。",
        "有人活着。\n很少。\n很累。\n也很安静。\n\n他们没有庆祝。\n"
        "没有唱歌。\n没有围着炉心喊出胜利。\n\n他们只是确认彼此还会"
        "呼吸。\n确认门外的风声终于低了一点。\n确认这座城还没有被从地图"
        "上抹掉。",
        "残火还在。\n\n它照不亮街道。\n也照不亮所有空床。\n\n但它还在。\n\n"
        "这就是炉城最后能拿出的答案。",
    ),
    "ending.player_ended.body": (
        "执政官终止了本局。\n\n炉心仍在燃烧。\n名册仍未写完。\n"
        "有些门还关着，有些床还空着。",
        "这不是系统宣判的失败。\n这是执政官亲手合上的档案。",
        "本局在执政官的命令下结束。\n\n城市没有替你做决定。\n风雪也"
        "没有。\n\n结束是一个选择。\n和所有选择一样，它会留下记录。",
    ),
    "ending.hard_fail.population_zero.body": (
        "最后一份名册没有被收回。\n\n炉心仍在夜里发出低声的震动，"
        "但已经没有人需要它。",
        "床铺空了。\n食堂空了。\n医疗站也空了。",
        "炉城没有倒塌。\n只是再也没有居民。",
        "第七霜落没有带走炉城的墙。\n它带走了墙里所有会说话的人。",
        "最后的炉火照亮了空屋。\n执政官的命令仍能被写下。\n"
        "但没有人再执行它。",
    ),
    "ending.hard_fail.core_collapse.body": (
        "炉心没有熄灭。\n\n它裂开了。",
        "红线之后，所有警告都变成了回声。\n炉城在一瞬间学会了什么叫"
        "真正的寒冷。",
        "过载撑过了一个夜晚。\n又撑过了一个夜晚。\n\n最后，它不再撑了。",
        "炉心外壳炸开的声音，比第七霜落更早抵达人们耳边。\n炉心压力"
        "越过了最后一道线。",
        "不是煤不够。\n不是人不够。\n\n是炉城最深处的东西，被命令继续"
        "燃烧，直到它拒绝再服从。",
    ),
    "ending.hard_fail.trust_exile.body": (
        "居民没有冲进执政厅。\n\n他们只是停下了。\n\n停下工作。\n停下"
        "等待。\n停下相信下一道命令会把他们带到明天。",
        "炉心还在烧。\n但执政官已经失去了让人靠近它的理由。\n\n最后一份"
        "公告贴在炉心旁。\n没有人撕下它。\n也没有人再读它。",
        "信任不是被砸碎的。\n它是一层一层冻住的，直到再也无法融开。",
        "炉城仍有煤。\n仍有墙。\n仍有名字。\n\n但居民不再相信执政官"
        "能带他们活下去。\n\n命令还在。\n城市已经不再回应。",
        "最后，炉城打开了门。\n\n不是为了迎接谁。\n而是为了让执政官离开。",
    ),
    "ending.hard_fail.panic_expelled.body": (
        "恐慌没有形状。\n\n它先出现在食堂队伍里。\n然后出现在医疗站门口。\n"
        "最后出现在每一个人看向炉心的眼睛里。",
        "炉城不是被风雪冲散的。\n它是从内部散开的。\n\n没有人再等待日结。\n"
        "没有人再相信下一道命令会比尖叫更快。",
        "有人抢煤。\n有人砸门。\n有人把孩子抱到炉心旁。\n\n执政官仍能"
        "下令。\n但恐慌已经比命令更快。",
        "城市没有立刻死亡。\n它只是失去了队列。\n失去了夜班。\n失去了把"
        "明天排进计划里的能力。\n\n第七霜落还没结束，炉城已经先乱了。",
        "最后，人们聚到炉心前。\n他们不再等待执政官开口。\n\n那不是"
        "等待。\n是判决。\n\n城门被打开。\n这一次，被推出去的是执政官。",
    ),
    "ending.hard_fail.closing": (
        "你失败了。\n\n这个炉城也许会迎来新的长官，也许就此陨落。\n"
        "但这一切都已经与你无关了。",
        "你可以选择重新开始，也可以就此放弃。\n选择权在你，执政官。",
        "本局结束。\n炉城没有再听见你的命令。\n\n它也许会继续挣扎，"
        "也许会在风雪里彻底沉下去。\n\n那是另一个故事。\n而你已经被"
        "写出这份档案。",
        "你的执政到此为止。\n炉心是否还能烧到明天，居民是否还能熬过"
        "下一夜，已经不再由你决定。\n\n风雪收下了你的失败。\n炉城收回了"
        "你的名字。",
    ),
    "ending.report.illness": (
        "仍有 {sick_total} 个病患躺在医疗站里。他们不会抱怨什么，只是"
        "闭紧开裂的嘴唇，等待下一次点名。",
        "病患不多，但每一次咳嗽都提醒人们：寒冬从来不只待在门外。",
        "医疗站终于有了片刻安静。那不是因为没人痛苦，只是因为最危险"
        "的一夜过去了。",
        "医疗站的灯还亮着，但它照见的不是安稳，而是太多人没能等到床位。",
    ),
    "ending.report.trust_panic": (
        "人们对你的信任托举着炉城，恐慌又一次次把它往下拽。",
        "居民仍然相信执政官，但他们也学会了害怕每一次公告。",
        "命令还能抵达岗位。至于它抵达的是信任，还是习惯，没有人急着回答。",
        "炉城安静下来。安静里有秩序，也有疲惫到无力反抗的恐惧。",
    ),
    "ending.report.core": (
        "炉心发出轻微的轰鸣，像一头终于熬过长夜的兽。",
        "炉心发出中度轰鸣。它撑住了城市，也让每个人听见自己离崩毁有多近。",
        "炉心发出沉重的轰鸣，像是在提醒执政官：它不是神迹，只是被逼到"
        "极限的机器。",
        "炉心还在烧。但没有人敢把这称作安稳。",
    ),
    "ending.report.coal_food": (
        "煤炭已经不多了，食物也只够继续数着天过。",
        "煤炭还够，食物也还够。够，不等于宽裕，只是让明天暂时有了形状。",
        "煤仓仍有余量，食物也能支撑一段时日。炉城终于可以把一部分目光"
        "从今晚移向明天。",
    ),
    "ending.report.future": (
        "不过，这已经不只是资源问题了。\n重要的是，炉城还保留着继续"
        "等下去的可能。",
        "炉城没有被拯救成一个温暖的地方。\n但它还没有被风雪彻底夺走未来。",
        "最终，人们没有得到春天。\n他们只是得到了继续等待春天的资格。",
    ),
    "ending.additional.death": (
        "死亡没有在第七霜落结束时停止。它只是从风雪里退回了名册。",
        "炉城活下来了，但有些名字只剩下被点名时的停顿。",
        "那些没能熬过最后七天的人，没有看到风停。炉城会继续走，但它"
        "必须带着他们留下的空位走。",
    ),
    "ending.additional.medical": (
        "医疗站没有完全倒下。可它也没有救下所有该被救下的人。",
        "病床曾经满到没有缝隙。有人在门外等到安静，也等到体温消失。",
        "医生和学徒撑住了灯。只是那盏灯照不到每一张脸。",
    ),
    "ending.additional.food": (
        "食堂的锅没有彻底冷下去。可每一次开饭，都像是在分配明天。",
        "饥饿没有立刻杀死炉城。它只是让每个人学会了用更少的声音说话。",
        "有人在最后七天里吃到了熟食。也有人只记得生食在嘴里留下的寒意。",
    ),
    "ending.additional.core": (
        "炉心没有崩毁。只是所有人都听见过它接近崩毁的声音。",
        "有些夜晚，炉城不是被供暖撑住的，而是被恐惧撑住的。",
        "过载让城市多活了一夜。炉城会记住这件事，也会记住它差点付出的代价。",
    ),
    "ending.additional.society": (
        "人们仍然执行命令。只是他们看向公告时，眼神已经不像从前。",
        "恐慌没有完全散去。它只是学会了在炉心旁边排队。",
        "信任没有消失。但它已经不是火焰，更像是一块勉强没有裂开的冰。",
    ),
    "ending.additional.housing": (
        "有些人熬过了第七霜落，却没有真正拥有一间能称作家的屋子。",
        "寒冷没有进入每一间房。可它进入过太多人的骨头。",
        "炉城还有墙。只是墙没有替每个人挡住那场风。",
    ),
    "ending.interrogation.general": (
        "执政官，炉城活了下来。\n\n但它不是自己活下来的。\n它是被煤、"
        "命令、恐惧、忍耐和死亡一起推过来的。\n\n现在，风停了。\n你还愿意"
        "看一眼自己留下的名册吗？",
        "你守住了炉心。\n\n可炉心不是城市的全部。\n那些没被炉火照到的"
        "人，也会进入档案。",
        "你可以说这是必要代价。\n\n炉城不会反驳。\n它只会把代价逐条保存。",
        "第七霜落结束后，命令仍然有效。\n\n只是有些人已经不在命令能抵达"
        "的地方。",
        "执政官，城市没有问你是否后悔。\n\n它只问你：如果寒冬再来一次，"
        "你还会这样做吗？",
    ),
    "ending.interrogation.high_victory": (
        "这已经是很好的结果。\n\n好到人们愿意把它叫作胜利。\n也沉到"
        "没有人敢忘记，那些没能走到胜利里的人。",
        "你把炉城带过了第七霜落。\n\n这不意味着每一道命令都是正确的。\n"
        "只意味着它们最终没有压垮这座城。",
    ),
    "ending.interrogation.cost": (
        "城市活下来了。\n\n但如果活着只是没有死去，那炉城还需要很久，"
        "才能重新成为一座城市。",
        "执政官，残缺也可以算作存活。\n\n只是炉城会记得，自己是怎样残缺"
        "下来的。",
        "你带他们越过了第七霜落。\n\n至于他们是否还愿意把这称为被拯救，"
        "档案没有替他们回答。",
    ),
    "ending.interrogation.ember": (
        "执政官，残火未灭。\n\n这不是胜利的号角。\n只是风雪退去后，"
        "废墟里还有一点红光。\n\n你可以把它叫作希望。\n也可以把它叫作"
        "尚未结束的代价。",
        "炉城还活着。\n\n可它活得太轻了。\n轻到一阵新的风，就可能把它"
        "再次吹散。",
    ),
}

_PENDING_LONG_TEXT_IDS = (
    "ending.route.final_oath.full_text",
    "ending.route.final_decree.full_text",
    "ending.route.oath.full_text",
    "ending.route.iron.full_text",
    "ending.old_city.full_text",
    "ending.children.full_text",
    "ending.death_handling.full_text",
    "ending.entertainment.full_text",
)
_PENDING_RUNTIME_TEXT_NOTES = {
    "ending.trace.children_protected": (
        "现有正文同时暗示互斥的医疗与工程学徒路线；"
        "分支适配文案封存前暂停运行时导入。"
    ),
    "ending.additional.medical.01": (
        "当前没有逐日医疗建筑及运行状态历史，无法证明疾病死亡当天"
        "存在医疗服务；补齐可验证历史前暂停运行时导入。"
    ),
    "ending.additional.medical.02": (
        "当前没有逐日医疗建筑、运行状态或容量历史，无法证明疾病死亡"
        "与床位溢出发生于实际医疗服务期间；补齐可验证历史前暂停运行时导入。"
    ),
}


def _expanded_runtime_text() -> dict[str, str]:
    text = dict(_RUNTIME_TEXT)
    for prefix, candidates in _TEXT_POOLS.items():
        for index, candidate in enumerate(candidates, start=1):
            text_id = f"{prefix}.{index:02d}"
            if text_id not in _PENDING_RUNTIME_TEXT_NOTES:
                text[text_id] = candidate
    return text


def build_ending_text_registry() -> TextRegistry:
    """Register sealed Patch 020 report text and user-confirmed death lines."""

    registry = TextRegistry()
    for text_id, text in _expanded_runtime_text().items():
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


def build_ending_pending_registry() -> PendingRegistry:
    """Keep unsealed or condition-conflicted ending text out of runtime."""

    registry = PendingRegistry()
    for entry_id in _PENDING_LONG_TEXT_IDS:
        registry.register(
            PendingEntry(
                entry_id=entry_id,
                status=ConfigStatus.TODO_TEXT,
                source=_SOURCE,
                note="009-C 完整长文案尚未封存；当前只使用已封存的一句式痕迹。",
            )
        )
    for entry_id, note in _PENDING_RUNTIME_TEXT_NOTES.items():
        registry.register(
            PendingEntry(
                entry_id=entry_id,
                status=ConfigStatus.PENDING,
                source=_SOURCE,
                note=note,
            )
        )
    return registry
