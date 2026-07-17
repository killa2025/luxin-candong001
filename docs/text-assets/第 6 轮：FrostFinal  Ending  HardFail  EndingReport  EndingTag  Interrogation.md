# 第 6 轮：FrostFinal / Ending / HardFail / EndingReport / EndingTag / Interrogation  
**全局导入说明：**凡可见性标记为“系统内部”的条目，默认属于开发注释、结构化标签、配置说明或测试口径，不直接进入玩家 runtime 文案库。只有明确标记为“玩家可见”“玩家可见（运行时模板）”或“通用”的文案资产进入正式 TextRegistry。 **终局边界：**第七霜落固定为第 49～55 天；第 55 天 end_day 后进入终局结算。第七霜落不是随机事件，也不新增独立硬失败轴。  
## 01_FrostFinal / 第七霜落阶段与日期口径  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------- | ----------- | ---- | ------------------------------------------------------- | ------------------- | --------- | ---------------- | ---- | --------------------------------- |
| frost.final.name | FrostFinal | 阶段名 | 第七霜落 | Patch 008-3 / 008-4 | 第七霜落阶段 | 已封存原文 | 通用 |  |
| frost.final.duration | FrostFinal | 阶段说明 | 第 49～55 天 | Patch 008-3 / 008-4 | 第七霜落固定时间 | 已封存原文 | 系统内部 | 玩家可见正文尽量使用“第七霜落期间 / 最后七天”等自然文本。 |
| frost.final.start_day | FrostFinal | 固定节点 | 第 49 天进入第七霜落。 | Patch 008-4 | 第七霜落固定时间 | 已封存原文 | 系统内部 |  |
| frost.final.ending_day | FrostFinal | 固定节点 | 第 55 天 end_day 后进入终局结算。 | Patch 008-4 | 第七霜落固定时间 | 已封存原文 | 系统内部 |  |
| frost.final.rule.fixed | FrostFinal | 内部规则 | 第七霜落不提前、不推迟，也不是随机事件。 | Patch 008-3 / 008-4 | 第七霜落固定时间 | 已封存原文 | 系统内部 |  |
| frost.final.rule.not_event | FrostFinal | 内部规则 | 第七霜落是终局天气阶段，不是普通事件，不占普通事件名额。 | Patch 008-3 / 第七批补表 | 第七霜落定位 | 已封存原文 | 系统内部 |  |
| frost.final.rule.not_new_game | FrostFinal | 内部规则 | 第七霜落是前 48 天准备的验收，不是重新开局。 | Patch 008-4 / 第七批补表 | 阶段定位 | 已封存原文 | 系统内部 |  |
| frost.final.rule.no_new_longline | FrostFinal | 内部规则 | 第 49～55 天不再开启新的普通承诺、旧城派阶段、离城倒计时、长期民生事件链、长期建设事件或长期社会改革线。 | Patch 008-4 / 第七批补表 | 禁止新开长线 | 用户确认覆盖项 | 系统内部 | 已存在的系统、建筑、炉律、后果和承诺到期结果继续结算。 |
| frost.final.rule.existing_action | FrostFinal | 内部规则 | 已有主动行动若冷却完成且系统允许，第七霜落期间仍可使用。 | 第七批补表 | 禁止新开长线 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 不得生成跨越终局的新承诺或新长线。 |
| ending.date.display_rule | Ending / UI | 显示规则 | 玩家可见终局文案使用“第 55 天”“第七霜落开始时”“第七霜落结束时”“最后七天”“霜落前夜”等自然文本。 | Patch 009-1 | 玩家可见日期口径 | 已封存原文 | 系统内部 | 不在玩家主文案中直接显示 D49 / D55 / D49～D55。 |
  
   
⸻  
   
## 02_FrostTemperature / 第七霜落温度表  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------ | ------------------------ | ------ | ------------------------------------------------------------------------------- | -------------------------- | --------- | ------- | ---- | ----------------------------------------------------- |
| frost.temperature.day49.real | FrostFinal / Temperature | 后台真实温度 | -66℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 | 所有停工、疾病、冻伤、死亡与终局验收计算读取真实温度。 |
| frost.temperature.day49.display | FrostFinal / Temperature | 玩家温度标签 | -70 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.day50.real | FrostFinal / Temperature | 后台真实温度 | -68℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 |  |
| frost.temperature.day50.display | FrostFinal / Temperature | 玩家温度标签 | -70 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.day51.real | FrostFinal / Temperature | 后台真实温度 | -70℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 |  |
| frost.temperature.day51.display | FrostFinal / Temperature | 玩家温度标签 | -70 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.day52.real | FrostFinal / Temperature | 后台真实温度 | -66℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 |  |
| frost.temperature.day52.display | FrostFinal / Temperature | 玩家温度标签 | -70 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.day53.real | FrostFinal / Temperature | 后台真实温度 | -72℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 |  |
| frost.temperature.day53.display | FrostFinal / Temperature | 玩家温度标签 | -70 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.day54.real | FrostFinal / Temperature | 后台真实温度 | -74℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 |  |
| frost.temperature.day54.display | FrostFinal / Temperature | 玩家温度标签 | -70 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.day55.real | FrostFinal / Temperature | 后台真实温度 | -76℃ | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 系统内部 |  |
| frost.temperature.day55.display | FrostFinal / Temperature | 玩家温度标签 | -80 级第七霜落 | Patch 008-3 / 第七批补表 | 第七霜落温度表 | 已封存原文 | 玩家可见 |  |
| frost.temperature.calculation_rule | FrostFinal / Temperature | 内部规则 | 所有计算读取后台真实温度；整十级标签只用于玩家理解。 | Patch 008-3 / 第七批补表 | 真实温度与显示标签 | 已封存原文 | 系统内部 | 玩家显示标签不得参与建筑停工、疾病、冻伤、死亡或终局验收。 |
| frost.temperature.formula | FrostFinal / Temperature | 内部公式 | 建筑有效温度 = 后台真实天气温度 + 炉心供暖修正 + 区域修正 + 建筑 / 住房 / 科技修正 + 过载修正 + heat 修正 + 终局炉心稳定修正。 | Patch 008-3 / 第七批补表；用户补充校正 | 建筑有效温度公式 | 用户确认覆盖项 | 系统内部 | 正式计算读取整数温度；具体科技修正值分别从已封存科技配置中读取，不得因公式列名自行补“炉心功率稳定”数值。 |
| frost.temperature.terminal_stability | FrostFinal / Tech | 科技效果说明 | 第 49～55 天且炉心运行时，建筑有效温度 +3；第 49～55 天且过载时，炉心压力增长额外 -5。 | Patch 008-3 / 第七批补表 | 终局炉心稳定 | 已封存原文 | 系统内部 | 不生成煤炭，不免疫炉心崩毁或人口归零。 |
  
   
⸻  
   
## 03_FrostDailyStatus / 第七霜落每日状态标签  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------------ | ------------------- | ----- | -------------------------------------- | ------------------- | --------- | ----- | ---- | ------------------------------------ |
| frost.status.heating_stable.name | FrostFinal / Status | 每日状态名 | 供暖稳定日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 可用于终局详情页或日志；主终局报告不直接逐日罗列。 |
| frost.status.heating_shortage.name | FrostFinal / Status | 每日状态名 | 供暖不足日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：furnace_underheated_day。 |
| frost.status.furnace_off.name | FrostFinal / Status | 每日状态名 | 炉心关闭日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：furnace_off_day。 |
| frost.status.critical_building_frozen.name | FrostFinal / Status | 每日状态名 | 关键建筑停工日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：critical_building_frozen_day。 |
| frost.status.medical_collapse.name | FrostFinal / Status | 每日状态名 | 医疗崩溃日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：medical_collapse_day。 |
| frost.status.starvation.name | FrostFinal / Status | 每日状态名 | 饥饿日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：starvation_day。 |
| frost.status.cold_house.name | FrostFinal / Status | 每日状态名 | 寒屋日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：cold_houses_day。 |
| frost.status.death.name | FrostFinal / Status | 每日状态名 | 死亡日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 |  |
| frost.status.mass_death.name | FrostFinal / Status | 每日状态名 | 大量死亡日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 内部标签方向：mass_death_day。 |
| frost.status.trust_crisis.name | FrostFinal / Status | 每日状态名 | 信任危机日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 |  |
| frost.status.panic_crisis.name | FrostFinal / Status | 每日状态名 | 恐慌危机日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 |  |
| frost.status.overload_redline.name | FrostFinal / Status | 每日状态名 | 过载红线日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 炉心压力达到红线，但尚未崩毁。 |
| frost.status.core_collapse.name | FrostFinal / Status | 每日状态名 | 炉心崩毁日 | Patch 008-4 | 每日状态标签 | 已封存原文 | 待判定 | 触发硬失败。 |
| frost.status.rule.not_failure | FrostFinal / Status | 内部规则 | 每日状态标签本身不自动判负；除非触发已封存硬失败条件，否则进入终局状态评级。 | Patch 008-4 / 第七批补表 | 每日状态标签 | 已封存原文 | 系统内部 |  |
  
   
⸻  
   
## 04_EndingRating / 六大系统与评级名称  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------------- | --------------- | ----- | ------------------------- | ------------------ | --------- | ------- | ---- | -------------------------------------------------- |
| ending.system.coal_core.name | Ending / Rating | 系统名 | 煤炭 / 炉心 | Patch 008-4 | 六大系统 | 已封存原文 | 通用 |  |
| ending.system.food.name | Ending / Rating | 系统名 | 食物 | Patch 008-4 | 六大系统 | 已封存原文 | 通用 |  |
| ending.system.housing_temperature.name | Ending / Rating | 系统名 | 住房 / 温度 | Patch 008-4 | 六大系统 | 已封存原文 | 通用 |  |
| ending.system.medical_disease.name | Ending / Rating | 系统名 | 医疗 / 疾病 | Patch 008-4 | 六大系统 | 已封存原文 | 通用 |  |
| ending.system.trust_panic.name | Ending / Rating | 系统名 | 信任 / 恐慌 | Patch 008-4 | 六大系统 | 已封存原文 | 通用 |  |
| ending.system.population_death.name | Ending / Rating | 系统名 | 人口 / 死亡 | Patch 008-4 | 六大系统 | 已封存原文 | 通用 |  |
| ending.rating.sufficient.name | Ending / Rating | 评级名 | 充足 | Patch 008-4 | 六大系统评级 | 已封存原文 | 通用 | 4 分。 |
| ending.rating.stable.name | Ending / Rating | 评级名 | 稳定 | Patch 008-4 | 六大系统评级 | 已封存原文 | 通用 | 3 分。 |
| ending.rating.barely.name | Ending / Rating | 评级名 | 勉强 | Patch 008-4 | 六大系统评级 | 已封存原文 | 通用 | 2 分。 |
| ending.rating.insufficient.name | Ending / Rating | 评级名 | 不足 | Patch 008-4 | 六大系统评级 | 已封存原文 | 通用 | 1 分。 |
| ending.rating.collapse.name | Ending / Rating | 评级名 | 崩坏 | Patch 008-4 | 六大系统评级 | 已封存原文 | 通用 | 0 分；系统崩坏不自动等于硬失败。 |
| ending.rating.total.label | Ending / Rating | UI 标签 | 六大系统总分：{total_score} / 24 | Patch 008-4；用户补充校正 | 六大系统评级 | 用户确认覆盖项 | 待判定 | 运行时变量模板，不得把字母 X 直接显示给玩家。默认终局主报告不展示大段数值表；可放终局档案详情页。 |
| ending.rating.rule.no_auto_fail | Ending / Rating | 内部规则 | 任一系统评级为崩坏，不自动新增硬失败。 | Patch 008-4 | 六大系统评级 | 已封存原文 | 系统内部 | 硬失败只由四项硬条件触发。 |
  
   
⸻  
   
## 05_EndingResult / 终局结果标题  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------ | ------ | ---- | ------- | ----------- | --------- | ----- | ---- | ---------------------------- |
| ending.title.hard_fail | Ending | 终局标题 | 炉城终止 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 | 通用硬失败标题；炉心崩毁、流放、驱逐可使用对应专属标题。 |
| ending.title.high_victory | Ending | 终局标题 | 炉城存续 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 |  |
| ending.title.standard_victory | Ending | 终局标题 | 炉城越冬 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 |  |
| ending.title.bitter_victory | Ending | 终局标题 | 炉城残胜 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 |  |
| ending.title.collapse_survival | Ending | 终局标题 | 崩坏幸存 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 | 不是失败。 |
| ending.title.ember_survival | Ending | 终局标题 | 残火未灭 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 | 不是失败。 |
| ending.title.player_ended | Ending | 终局标题 | 执政官终止执政 | Patch 009-1 | 终局标题 | 已封存原文 | 玩家可见 | 玩家主动结束不是系统硬失败。 |
  
   
⸻  
   
## 06_HardFail / 系统硬失败文案池  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------------ | ----------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | --------- | ----- | ---- | --------------------------------------------------------------------------------------- |
| ending.hard_fail.population_zero.title | Ending / HardFail | 失败标题 | 炉城终止 | Patch 009-1 | 人口归零失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.population_zero.body_pool | Ending / HardFail | 失败主文案池 | 最后一份名册没有被收回。\\n\\n炉心仍在夜里发出低声的震动，但已经没有人需要它。\\n床铺空了。\\n食堂空了。\\n医疗站也空了。\\n\\n炉城没有倒塌。\\n只是再也没有居民。\\n\\n第七霜落没有带走炉城的墙。\\n它带走了墙里所有会说话的人。\\n\\n最后的炉火照亮了空屋。\\n执政官的命令仍能被写下。\\n但没有人再执行它。 | Patch 009-1 | 人口归零失败 | 已封存原文 | 玩家可见 | 文案池可整体使用，或按池内封存段落选择。含“第七霜落没有带走……”的段落仅在第七霜落期间或 D55 结算时可选；第 49 天前人口归零时，只从不依赖第七霜落日期的段落中选择。 |
| ending.hard_fail.population_zero.reason | Ending / HardFail | 一句话原因 | 炉城最后一次点名时，没有人回答。 | Patch 009-1 | 人口归零失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.core_collapse.title | Ending / HardFail | 失败标题 | 炉心崩毁 | Patch 009-1 | 炉心崩毁失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.core_collapse.body_pool | Ending / HardFail | 失败主文案池 | 炉心没有熄灭。\\n\\n它裂开了。\\n\\n红线之后，所有警告都变成了回声。\\n炉城在一瞬间学会了什么叫真正的寒冷。\\n\\n过载撑过了一个夜晚。\\n又撑过了一个夜晚。\\n\\n最后，它不再撑了。\\n\\n炉心外壳炸开的声音，比第七霜落更早抵达人们耳边。\\n炉心压力越过了最后一道线。\\n\\n不是煤不够。\\n不是人不够。\\n\\n是炉城最深处的东西，被命令继续燃烧，直到它拒绝再服从。 | Patch 009-1 | 炉心崩毁失败 | 已封存原文 | 玩家可见 | 含“比第七霜落更早……”的段落只适用于第七霜落开始前的炉心崩毁；第七霜落期间崩毁时不得选择该段。 |
| ending.hard_fail.core_collapse.reason | Ending / HardFail | 一句话原因 | 炉心越过红线后，再也没有回到执政官的命令里。 | Patch 009-1 | 炉心崩毁失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.trust_exile.title | Ending / HardFail | 失败标题 | 执政官被流放 | Patch 009-1 | 信任失败 | 已封存原文 | 玩家可见 | 信任失败是玩家失败，不等于炉城立即毁灭。 |
| ending.hard_fail.trust_exile.body_pool | Ending / HardFail | 失败主文案池 | 居民没有冲进执政厅。\\n\\n他们只是停下了。\\n\\n停下工作。\\n停下等待。\\n停下相信下一道命令会把他们带到明天。\\n\\n炉心还在烧。\\n但执政官已经失去了让人靠近它的理由。\\n\\n最后一份公告贴在炉心旁。\\n没有人撕下它。\\n也没有人再读它。\\n\\n信任不是被砸碎的。\\n它是一层一层冻住的，直到再也无法融开。\\n\\n炉城仍有煤。\\n仍有墙。\\n仍有名字。\\n\\n但居民不再相信执政官能带他们活下去。\\n\\n命令还在。\\n城市已经不再回应。\\n\\n最后，炉城打开了门。\\n\\n不是为了迎接谁。\\n而是为了让执政官离开。 | Patch 009-1 | 信任失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.trust_exile.reason | Ending / HardFail | 一句话原因 | 居民不再相信你有资格继续带领他们。 | Patch 009-1 | 信任失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.panic_expelled.title | Ending / HardFail | 失败标题 | 执政官被驱逐 | Patch 009-1 | 恐慌失败 | 已封存原文 | 玩家可见 | 通用恐慌失败文案不得混入南方传言或旧城派。 |
| ending.hard_fail.panic_expelled.body_pool | Ending / HardFail | 失败主文案池 | 恐慌没有形状。\\n\\n它先出现在食堂队伍里。\\n然后出现在医疗站门口。\\n最后出现在每一个人看向炉心的眼睛里。\\n\\n炉城不是被风雪冲散的。\\n它是从内部散开的。\\n\\n没有人再等待日结。\\n没有人再相信下一道命令会比尖叫更快。\\n\\n有人抢煤。\\n有人砸门。\\n有人把孩子抱到炉心旁。\\n\\n执政官仍能下令。\\n但恐慌已经比命令更快。\\n\\n城市没有立刻死亡。\\n它只是失去了队列。\\n失去了夜班。\\n失去了把明天排进计划里的能力。\\n\\n第七霜落还没结束，炉城已经先乱了。\\n\\n最后，人们聚到炉心前。\\n他们不再等待执政官开口。\\n\\n那不是等待。\\n是判决。\\n\\n城门被打开。\\n这一次，被推出去的是执政官。 | Patch 009-1 | 恐慌失败 | 已封存原文 | 玩家可见 | 含“第七霜落还没结束……”的段落仅适用于第 49～55 天；此前触发恐慌失败时不得选择。 |
| ending.hard_fail.panic_expelled.reason | Ending / HardFail | 一句话原因 | 居民害怕你，胜过害怕门外的风雪。 | Patch 009-1 | 恐慌失败 | 已封存原文 | 玩家可见 |  |
| ending.hard_fail.closing_pool | Ending / HardFail | 通用收束句池 | 你失败了。\\n\\n这个炉城也许会迎来新的长官，也许就此陨落。\\n但这一切都已经与你无关了。\\n\\n你可以选择重新开始，也可以就此放弃。\\n选择权在你，执政官。\\n\\n本局结束。\\n炉城没有再听见你的命令。\\n\\n它也许会继续挣扎，也许会在风雪里彻底沉下去。\\n\\n那是另一个故事。\\n而你已经被写出这份档案。\\n\\n你的执政到此为止。\\n炉心是否还能烧到明天，居民是否还能熬过下一夜，已经不再由你决定。\\n\\n风雪收下了你的失败。\\n炉城收回了你的名字。 | Patch 009-1 | 硬失败通用结尾 | 已封存原文 | 玩家可见 | 从池中选择一段；不强行断言炉城必然灭亡，不羞辱玩家。 |
  
   
⸻  
   
## 07_PlayerEnded / 玩家主动结束文案池  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ----------------------------- | -------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | --------- | ----- | ---- | ----------------- |
| ending.player_ended.title | Ending / PlayerEnded | 标题 | 执政官终止执政 | Patch 009-1 | 玩家主动结束 | 已封存原文 | 玩家可见 |  |
| ending.player_ended.body_pool | Ending / PlayerEnded | 主文案池 | 执政官终止了本局。\\n\\n炉心仍在燃烧。\\n名册仍未写完。\\n有些门还关着，有些床还空着。\\n\\n这不是系统宣判的失败。\\n这是执政官亲手合上的档案。\\n\\n本局在执政官的命令下结束。\\n\\n城市没有替你做决定。\\n风雪也没有。\\n\\n结束是一个选择。\\n和所有选择一样，它会留下记录。 | Patch 009-1 | 玩家主动结束 | 已封存原文 | 玩家可见 |  |
| ending.player_ended.status | Ending / PlayerEnded | 一句话封存状态 | 本局由执政官亲手封存。 | Patch 009-1 | 玩家主动结束 | 已封存原文 | 玩家可见 |  |
| ending.player_ended.closing | Ending / PlayerEnded | 收束句 | 炉城档案封存。\\n\\n不是因为所有问题都有了答案。\\n而是因为执政官决定，不再继续追问。 | Patch 009-1 | 玩家主动结束 | 已封存原文 | 玩家可见 |  |
| ending.player_ended.rule | Ending / PlayerEnded | 内部规则 | 玩家主动结束不是系统硬失败，不进入 hard_fail。 | Patch 008-4 / 009-1 / 009-2 | 玩家主动结束 | 已封存原文 | 系统内部 | 可显示 0～1 条重大状态附加句。 |
  
   
⸻  
   
## 08_SurvivalEnding / 存活结局主文案池  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------- | ----------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | --------- | ----- | ---- | ------------------------- |
| ending.high_victory.body_pool | Ending / Survival | 高质量胜利文案池 | 第七霜落结束了。\\n\\n炉心仍在燃烧。\\n食堂重新排起队。\\n医疗站的灯没有熄。\\n清晨点名时，大多数名字仍有人回答。\\n\\n这是一场少见的胜利。\\n\\n只是还有人记得，最初那些在雪地里冻硬的身躯。\\n他们没有走到最终。\\n却把空出来的位置，留给了后来的人。\\n\\n风雪退去时，炉城没有欢呼。\\n\\n人们只是走出门，确认烟囱还在，名册还在，孩子还在。\\n有人把冻硬的门闩重新推开。\\n有人开始计算下一顿饭。\\n\\n胜利没有声音。\\n它只是让城市还能继续做明天的事。\\n\\n第七霜落没能把炉城压碎。\\n\\n煤仓没有彻底见底。\\n病床没有完全溢出。\\n炉心没有越线。\\n大多数人仍在自己的床上醒来。\\n\\n这已经足够接近胜利。\\n\\n只是胜利也有背面。\\n背面写着那些早在第七霜落之前，就倒在路上、病床上、雪地里的人。 | Patch 009-1 | 高质量胜利 | 已封存原文 | 玩家可见 | 文案池按终局种子或受控随机选取；不能写成纯粹欢呼。 |
| ending.standard_victory.body_pool | Ending / Survival | 标准胜利文案池 | 第七霜落结束了。\\n\\n炉心还在烧。\\n城市还在运转。\\n有人死去，有人病倒，有人再也不能回到岗位上。\\n\\n炉城没有散。\\n\\n只是越过寒冬的人，必须从明天开始，和那些空床一起生活。\\n\\n最后一夜过去时，炉心旁仍有人值守。\\n\\n煤仓不算充足。\\n食堂不算安稳。\\n医疗站也不再像从前那样干净。\\n\\n可城市还在。\\n\\n这句话很沉。\\n沉到足够压住欢呼。\\n\\n第七霜落没有给出宽恕。\\n它只给出结果。\\n\\n炉城活下来了。\\n\\n执政官的命令、居民的忍耐、炉心里的煤，共同把这座城推过了第 55 天。\\n\\n推过去之后，人们才发现，自己仍然站在寒冬里。 | Patch 009-1 | 标准胜利 | 已封存原文 | 玩家可见 |  |
| ending.bitter_victory.body_pool | Ending / Survival | 惨胜文案池 | 第七霜落结束了。\\n\\n炉心仍在燃烧。\\n只是围在炉心旁的人少了很多。\\n\\n名册被翻到最后一页。\\n活着的人没有欢呼。\\n\\n他们只是看着空出来的床位，等执政官宣布下一条命令。\\n\\n城市活下来了。\\n\\n这句话是真的。\\n但它太轻，压不住雪下那些名字。\\n\\n炉城越过了第七霜落。\\n代价已经写进每一间空屋。\\n\\n第七霜落没有杀死炉城。\\n\\n它只是拿走了太多东西。\\n健康的人。\\n相信的人。\\n敢大声说话的人。\\n\\n炉心还在烧。\\n可炉城的影子比从前短了。 | Patch 009-1 | 惨胜 | 已封存原文 | 玩家可见 |  |
| ending.collapse_survival.body_pool | Ending / Survival | 崩坏幸存文案池 | 第七霜落结束了。\\n\\n炉城没有死。\\n这句话必须说得很小声。\\n\\n炉心还在烧。\\n但它烧着的，不再像一座完整的城市。\\n\\n食堂还能排队。\\n只是队伍里少了太多熟悉的脸。\\n\\n医疗站还开着。\\n只是里面的人不再相信所有人都能轮到床位。\\n\\n命令仍能传下去。\\n只是每一道命令，都要越过恐惧、饥饿、疲惫和沉默。\\n\\n炉城活过了第七霜落。\\n但它不是胜利地站在那里。\\n\\n它是跪着，靠在炉心旁，勉强没有倒下。\\n\\n风雪没有彻底拿走它。\\n可风雪也没有把它完整地还回来。 | Patch 009-1 | 崩坏幸存 | 已封存原文 | 玩家可见 | 崩坏幸存不是失败。 |
| ending.ember_survival.body_pool | Ending / Survival | 残火未灭文案池 | 第七霜落结束了。\\n\\n炉心还剩一点火。\\n\\n那点火不够温暖一座城。\\n只够证明炉城还没有完全死去。\\n\\n有人活着。\\n很少。\\n很累。\\n也很安静。\\n\\n他们没有庆祝。\\n没有唱歌。\\n没有围着炉心喊出胜利。\\n\\n他们只是确认彼此还会呼吸。\\n确认门外的风声终于低了一点。\\n确认这座城还没有被从地图上抹掉。\\n\\n残火还在。\\n\\n它照不亮街道。\\n也照不亮所有空床。\\n\\n但它还在。\\n\\n这就是炉城最后能拿出的答案。 | Patch 009-1 | 残火未灭 | 已封存原文 | 玩家可见 | 残火未灭不是失败。 |
  
   
⸻  
   
## 09_NarrativeReport / 叙事式炉城报告  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------- | --------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | --------- | ------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ending.report.template | Ending / Report | 运行时报告模板 | 你带领 {start_population} 个人走入寒冬。\\n{death_record_sentence}\\n最后七天里，第七霜落又带走了 {frostfall_deaths} 个再过几天就能见到曙光的人。\\n\\n{illness_sentence}\\n\\n{trust_panic_sentence}\\n\\n{core_sentence}\\n\\n{coal_food_sentence}\\n\\n{future_sentence} | Patch 009-1；用户补充校正 | 叙事式炉城报告 | 用户确认覆盖项 | 玩家可见（运行时模板） | death_record_sentence 必须根据本局实际死亡处理方式选择；墓园、冷藏坑、余烬名册不得以“墓园 / 冷藏坑 / 余烬名册”斜杠形式直接显示。若没有已封存的对应句，标 TODO_TEXT，不得自行创作。原 hope_sentence 仅为文学句池接口，正式字段改为 future_sentence，不得恢复 hope_state。 |
| ending.report.illness.pool | Ending / Report | 病患句池 | 仍有 {sick_total} 个病患躺在医疗站里。他们不会抱怨什么，只是闭紧开裂的嘴唇，等待下一次点名。\\n\\n病患不多，但每一次咳嗽都提醒人们：寒冬从来不只待在门外。\\n\\n医疗站终于有了片刻安静。那不是因为没人痛苦，只是因为最危险的一夜过去了。\\n\\n医疗站的灯还亮着，但它照见的不是安稳，而是太多人没能等到床位。 | Patch 009-1 | 病患句池 | 已封存原文 | 玩家可见 | 根据医疗 / 疾病状态选 1 条。 |
| ending.report.trust_panic.pool | Ending / Report | 信任 / 恐慌句池 | 人们对你的信任托举着炉城，恐慌又一次次把它往下拽。\\n\\n居民仍然相信执政官，但他们也学会了害怕每一次公告。\\n\\n命令还能抵达岗位。至于它抵达的是信任，还是习惯，没有人急着回答。\\n\\n炉城安静下来。安静里有秩序，也有疲惫到无力反抗的恐惧。 | Patch 009-1 | 信任 / 恐慌句池 | 已封存原文 | 玩家可见 |  |
| ending.report.core.pool | Ending / Report | 炉心句池 | 炉心发出轻微的轰鸣，像一头终于熬过长夜的兽。\\n\\n炉心发出中度轰鸣。它撑住了城市，也让每个人听见自己离崩毁有多近。\\n\\n炉心发出沉重的轰鸣，像是在提醒执政官：它不是神迹，只是被逼到极限的机器。\\n\\n炉心还在烧。但没有人敢把这称作安稳。 | Patch 009-1 | 炉心句池 | 已封存原文 | 玩家可见 |  |
| ending.report.coal_food.pool | Ending / Report | 煤炭 / 食物句池 | 煤炭已经不多了，食物也只够继续数着天过。\\n\\n煤炭还够，食物也还够。够，不等于宽裕，只是让明天暂时有了形状。\\n\\n煤仓仍有余量，食物也能支撑一段时日。炉城终于可以把一部分目光从今晚移向明天。\\n\\n食堂还能开火，但队伍比从前安静。人们学会了不问下一顿能不能准时到来。 | Patch 009-1 | 煤炭 / 食物句池 | 已封存原文 | 玩家可见 |  |
| ending.report.future.pool | Ending / Report | 延续句池 | 不过，这已经不只是资源问题了。\\n重要的是，炉城还保留着继续等下去的可能。\\n\\n炉城没有被拯救成一个温暖的地方。\\n但它还没有被风雪彻底夺走未来。\\n\\n最终，人们没有得到春天。\\n他们只是得到了继续等待春天的资格。 | Patch 009-1 | 原希望句池 | 用户确认覆盖项 | 玩家可见 | “希望”只作为文学表达，不建立 hope_state、希望值或独立状态轴。 |
| ending.report.rule.no_big_table | Ending / Report | 内部规则 | 默认终局报告以叙事文本为主，不展示大段六大系统数值表。 | Patch 009-1 / 009-2 | 终局报告结构 | 已封存原文 | 系统内部 | 完整数值可放调试或“查看终局档案详情”。 |
  
   
⸻  
   
## 10_AdditionalSentence / 重大状态附加句池  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------ | ------------------- | ----------- | --------------------------------------------------------------------------------------------------------- | ----------- | ----------- | ----- | ---- | -- |
| ending.additional.death.pool | Ending / Additional | 死亡附加句池 | 死亡没有在第七霜落结束时停止。它只是从风雪里退回了名册。\\n\\n炉城活下来了，但有些名字只剩下被点名时的停顿。\\n\\n那些没能熬过最后七天的人，没有看到风停。炉城会继续走，但它必须带着他们留下的空位走。 | Patch 009-1 | 死亡相关附加句池 | 已封存原文 | 玩家可见 |  |
| ending.additional.medical.pool | Ending / Additional | 医疗附加句池 | 医疗站没有完全倒下。可它也没有救下所有该被救下的人。\\n\\n病床曾经满到没有缝隙。有人在门外等到安静，也等到体温消失。\\n\\n医生和学徒撑住了灯。只是那盏灯照不到每一张脸。 | Patch 009-1 | 医疗相关附加句池 | 已封存原文 | 玩家可见 |  |
| ending.additional.food.pool | Ending / Additional | 食物附加句池 | 食堂的锅没有彻底冷下去。可每一次开饭，都像是在分配明天。\\n\\n饥饿没有立刻杀死炉城。它只是让每个人学会了用更少的声音说话。\\n\\n有人在最后七天里吃到了熟食。也有人只记得生食在嘴里留下的寒意。 | Patch 009-1 | 食物相关附加句池 | 已封存原文 | 玩家可见 |  |
| ending.additional.core.pool | Ending / Additional | 炉心 / 供暖附加句池 | 炉心没有崩毁。只是所有人都听见过它接近崩毁的声音。\\n\\n有些夜晚，炉城不是被供暖撑住的，而是被恐惧撑住的。\\n\\n过载让城市多活了一夜。炉城会记住这件事，也会记住它差点付出的代价。 | Patch 009-1 | 炉心 / 供暖附加句池 | 已封存原文 | 玩家可见 |  |
| ending.additional.society.pool | Ending / Additional | 信任 / 恐慌附加句池 | 人们仍然执行命令。只是他们看向公告时，眼神已经不像从前。\\n\\n恐慌没有完全散去。它只是学会了在炉心旁边排队。\\n\\n信任没有消失。但它已经不是火焰，更像是一块勉强没有裂开的冰。 | Patch 009-1 | 信任 / 恐慌附加句池 | 已封存原文 | 玩家可见 |  |
| ending.additional.housing.pool | Ending / Additional | 住房 / 寒冷附加句池 | 有些人熬过了第七霜落，却没有真正拥有一间能称作家的屋子。\\n\\n寒冷没有进入每一间房。可它进入过太多人的骨头。\\n\\n炉城还有墙。只是墙没有替每个人挡住那场风。 | Patch 009-1 | 住房 / 寒冷附加句池 | 已封存原文 | 玩家可见 |  |
  
   
⸻  
   
## 11_Interrogation / 执政官拷问文案池  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------------- | ---------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | ------------ | ----- | ---- | --------------------- |
| ending.interrogation.general.pool | Ending / Interrogation | 通用拷问池 | 执政官，炉城活了下来。\\n\\n但它不是自己活下来的。\\n它是被煤、命令、恐惧、忍耐和死亡一起推过来的。\\n\\n现在，风停了。\\n你还愿意看一眼自己留下的名册吗？\\n\\n你守住了炉心。\\n\\n可炉心不是城市的全部。\\n那些没被炉火照到的人，也会进入档案。\\n\\n你可以说这是必要代价。\\n\\n炉城不会反驳。\\n它只会把代价逐条保存。\\n\\n第七霜落结束后，命令仍然有效。\\n\\n只是有些人已经不在命令能抵达的地方。\\n\\n执政官，城市没有问你是否后悔。\\n\\n它只问你：如果寒冬再来一次，你还会这样做吗？ | Patch 009-1 | 通用拷问文案池 | 已封存原文 | 玩家可见 | 最终选 1 条主题。 |
| ending.interrogation.high_victory.pool | Ending / Interrogation | 高质量胜利拷问池 | 这已经是很好的结果。\\n\\n好到人们愿意把它叫作胜利。\\n也沉到没有人敢忘记，那些没能走到胜利里的人。\\n\\n你把炉城带过了第七霜落。\\n\\n这不意味着每一道命令都是正确的。\\n只意味着它们最终没有压垮这座城。 | Patch 009-1 | 高质量胜利拷问池 | 已封存原文 | 玩家可见 |  |
| ending.interrogation.cost.pool | Ending / Interrogation | 惨胜 / 崩坏幸存拷问池 | 城市活下来了。\\n\\n但如果活着只是没有死去，那炉城还需要很久，才能重新成为一座城市。\\n\\n执政官，残缺也可以算作存活。\\n\\n只是炉城会记得，自己是怎样残缺下来的。\\n\\n你带他们越过了第七霜落。\\n\\n至于他们是否还愿意把这称为被拯救，档案没有替他们回答。 | Patch 009-1 | 惨胜 / 崩坏幸存拷问池 | 已封存原文 | 玩家可见 |  |
| ending.interrogation.ember.pool | Ending / Interrogation | 残火未灭拷问池 | 执政官，残火未灭。\\n\\n这不是胜利的号角。\\n只是风雪退去后，废墟里还有一点红光。\\n\\n你可以把它叫作希望。\\n也可以把它叫作尚未结束的代价。\\n\\n炉城还活着。\\n\\n可它活得太轻了。\\n轻到一阵新的风，就可能把它再次吹散。 | Patch 009-1 | 残火未灭拷问池 | 已封存原文 | 玩家可见 | “希望”为文学用词，不建立希望状态字段。 |
| ending.interrogation.hard_fail.pool | Ending / Interrogation | 硬失败拷问池 | 失败已经发生。\\n\\n现在剩下的问题不是能不能挽回。\\n而是你是否看清，它是从哪一天开始变得无法挽回。\\n\\n炉城没有要求你完美。\\n\\n它只要求你在每一次警告之后，仍然知道自己在命令什么。\\n\\n风雪是灾难。\\n\\n但不是每一场失败，都只属于风雪。 | Patch 009-1 | 硬失败拷问池 | 已封存原文 | 玩家可见 | 硬失败可只使用收束句，不强制显示完整拷问。 |
  
   
⸻  
   
## 12_InstitutionTrace / 重大炉律与路线痕迹摘要  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------- | -------------- | ------ | --------------------------------------------------------------------------- | ------------------ | ---------- | ------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| ending.trace.child_labor | Ending / Trace | 儿童辅工摘要 | 你签署了儿童辅工。孩子们用细嫩的手搬运木料、整理仓库，甚至在最冷的日子里跟着成年人走近风雪。炉城因此多撑住了一些时刻，而这些时刻会永远记得他们的年纪。 | Patch 009-2 | 儿童线摘要 | 已封存原文 | 玩家可见 | 儿童伤害或死亡由重大状态标签另行处理，不在此重复。 |
| ending.trace.children_protected | Ending / Trace | 儿童保护摘要 | 你修建了儿童保护所。孩子们在炉火旁学会数数、识字，拿起尺子、绷带和小小的手术刀。炉城没有急着把他们变成工人，而是把未来暂时藏进了更暖的屋子里。 | Patch 009-2 | 儿童线摘要 | 已封存原文 | 玩家可见 |  |
| ending.trace.cemetery | Ending / Trace | 墓园摘要 | 你为死者留下了墓园。那些名字没有只停在数字里，人们仍能在风雪间找到一处地方，承认他们曾经活过。 | Patch 009-2 | 死亡处理线摘要 | 已封存原文 | 玩家可见 |  |
| ending.trace.cold_pit | Ending / Trace | 冷藏坑摘要 | 你修建了冷藏坑。死者没有立刻离开炉城，他们被安置在冰冷的秩序里，等待城市决定如何继续面对他们。 | Patch 009-2 | 死亡处理线摘要 | 已封存原文 | 玩家可见 |  |
| ending.trace.entertainment | Ending / Trace | 娱乐减压摘要 | 你给炉城留下了喘息的地方。有人在小酒馆、火盆或赌桌旁短暂忘记寒冷；只是忘记不是解决，笑声也不能替炉心添煤。 | Patch 009-2；用户补充校正 | 娱乐 / 减压线摘要 | 用户确认覆盖项 | 玩家可见 | 正式建筑名统一为“小酒馆”；正文内容仍按 A 干净封存版，只校正最新正式命名。若已触发 sedation_city 等重大后果，则不显示普通摘要。 |
| ending.trace.oath_route | Ending / Trace | 誓言路线痕迹 | 你让炉城用誓言、悼亡、共食和名册维系彼此。它们不能让煤变多，也不能让死人回来，却让一些人在最冷的时候仍愿意留下。 | Patch 009-2 | 誓言路线痕迹 | 已封存原文 | 玩家可见 | 不能仅因签署路线入口“守炉誓言”就显示完整摘要；只有本局实际签署并使用了对应誓言路线炉律，或形成 oath_governance / final_oath 等路线结果时才可显示。正文提及的悼亡、共食、名册必须与本局实际签署内容匹配，不得声称玩家实施过未签署炉律。不展开终火誓约专属长文案。 |
| ending.trace.iron_route | Ending / Trace | 铁腕路线痕迹 | 你让炉城用巡查、点名、公告和留置维持秩序。它们不能让恐惧消失，却让恐惧学会排队，学会在命令前暂时低头。 | Patch 009-2 | 铁腕路线痕迹 | 已封存原文 | 玩家可见 | 不能仅因签署路线入口“炉城巡令”就显示完整摘要；只有本局实际签署并使用了对应铁腕路线炉律，或形成 iron_governance / final_decree 等路线结果时才可显示。正文提及的点名、公告、留置必须与本局实际签署内容匹配，不得声称玩家实施过未签署炉律。不展开最高戒令专属长文案。 |
| ending.trace.old_city | Ending / Trace | 旧城派痕迹 | 有人曾相信炉城之外还有另一条路。有人留下，有人离开，也有人只是把怀疑压回心里，继续围着炉心等待天亮。 | Patch 009-2 | 旧城派痕迹 | 已封存原文 | 玩家可见 | 通用恐慌文案仍不得混入南方传言。 |
| ending.trace.max_count | Ending / Trace | 内部规则 | 重大炉律 / 路线痕迹摘要默认最多 1 条；特殊情况下最多 2 条。 | Patch 009-2 | 摘要数量 | 已封存原文 | 系统内部 | 特殊组合：儿童线 + 路线痕迹；死亡处理线 + 旧城派重大结果。 |
| ending.trace.priority | Ending / Trace | 内部规则 | 儿童线 > 死亡处理线 > 誓言 / 铁腕路线痕迹 > 旧城派痕迹 > 娱乐 / 减压线。 | Patch 009-2 | 摘要数量 | 已封存原文 | 系统内部 | 若同主题已有重大状态附加句，普通摘要句不显示。 |
  
   
⸻  
   
## 13_EndingTag / 终局结果与重大状态标签  
**13.1 终局结果标签**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------- | ------------ | ---- | ----------------- | ------------------- | --------- | ----- | ---- | ------------- |
| ending.tag.hard_fail | Ending / Tag | 结果标签 | hard_fail | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 |  |
| ending.tag.player_ended | Ending / Tag | 结果标签 | player_ended | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 |  |
| ending.tag.high_victory | Ending / Tag | 结果标签 | high_victory | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 |  |
| ending.tag.standard_victory | Ending / Tag | 结果标签 | standard_victory | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 |  |
| ending.tag.bitter_victory | Ending / Tag | 结果标签 | bitter_victory | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 |  |
| ending.tag.collapse_survival | Ending / Tag | 结果标签 | collapse_survival | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 | 不是 hard_fail。 |
| ending.tag.ember_survival | Ending / Tag | 结果标签 | ember_survival | Patch 008-4 / 009-2 | 终局结果标签 | 已封存原文 | 系统内部 | 不是 hard_fail。 |
  
**13.2 硬失败类型标签**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------- | ------------ | ----- | --------------- | ------------------- | --------- | ----- | ---- | ------------------- |
| ending.fail.population_zero | Ending / Tag | 硬失败标签 | population_zero | Patch 008-4 / 009-2 | 硬失败类型 | 已封存原文 | 系统内部 | 存活人口归零。 |
| ending.fail.core_collapse | Ending / Tag | 硬失败标签 | core_collapse | Patch 008-4 / 009-2 | 硬失败类型 | 已封存原文 | 系统内部 | 炉心崩毁。 |
| ending.fail.trust_exile | Ending / Tag | 硬失败标签 | trust_exile | Patch 008-4 / 009-2 | 硬失败类型 | 已封存原文 | 系统内部 | 信任归零且未被终火誓约承接。 |
| ending.fail.panic_expelled | Ending / Tag | 硬失败标签 | panic_expelled | Patch 008-4 / 009-2 | 硬失败类型 | 已封存原文 | 系统内部 | 恐慌达到 100 且未被最高戒令压制。 |
  
**13.3 六大系统重大标签**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------- | ------------ | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | --------- | ----- | ---- | -------------------- |
| ending.tag.coal_core.group | Ending / Tag | 内部标签组 | coal_secure：煤炭 / 炉心稳定；coal_desperate：煤炭 / 炉心勉强或更差；cold_engine：多日供暖不足或炉心关闭；redline_survivor：触发炉心红线但未崩毁；overload_burned_city：终局长期依赖过载；heat_last_stand：多次救命式 heat。 | Patch 009-2 | 煤炭 / 炉心标签 | 已封存原文 | 系统内部 | 使用 1 次 heat 不进入终局标签。 |
| ending.tag.food.group | Ending / Tag | 内部标签组 | food_secure：食物稳定；famine_survivor：长期食物压力或多日饥饿；famine_city：严重饥荒或饥饿造成大量死亡。 | Patch 009-2 | 食物标签 | 已封存原文 | 系统内部 | 短暂食物不足不进入终局审判。 |
| ending.tag.housing.group | Ending / Tag | 内部标签组 | housed_city：住房稳定且无住所为零；cold_houses：多日寒屋；frozen_homeless：长期无住所寒冷暴露并造成严重后果；city_continuity_broken：人口低于城市连续性参考线。 | Patch 009-2 | 住房 / 寒冷标签 | 已封存原文 | 系统内部 | 城市连续性崩坏不是硬失败。 |
| ending.tag.medical.group | Ending / Tag | 内部标签组 | medical_secure：医疗稳定；medical_strained：医疗勉强；medical_collapse：医疗不足或多日崩溃；silent_hospital：医院长期停治或无法承接重症；survived_with_disabled：高伤残下存活。 | Patch 009-2 | 医疗 / 疾病标签 | 已封存原文 | 系统内部 |  |
| ending.tag.society.group | Ending / Tag | 内部标签组 | trusted_regime：社会稳定；broken_society：社会危机或崩坏；oath_carried_zero_trust：终火誓约承接信任归零；decree_carried_panic：最高戒令压制恐慌失败。 | Patch 009-2 | 信任 / 恐慌标签 | 已封存原文 | 系统内部 | 终章炉律不删除原始数值。 |
| ending.tag.population.group | Ending / Tag | 内部标签组 | low_death：死亡比例较低；mass_death：终局大量死亡；grave_city：累计死亡达到高比例或遗体系统长期崩坏；deathless_frost：第七霜落期间无死亡。 | Patch 009-2 | 人口 / 死亡标签 | 已封存原文 | 系统内部 | 单次死亡不触发 mass_death。 |
  
**13.4 制度、路线与重大决定标签**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------- | ------------ | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- | ----------- | ------- | ---- | ---------------------------------------------------------------- |
| ending.tag.children.group | Ending / Tag | 内部标签组 | child_labor_low、child_labor_full、child_labor_harm、children_protected、children_at_risk、children_lost、medical_apprentices、engineering_apprentices。 | Patch 009-2 | 儿童 / 人力统筹标签 | 已封存原文 | 系统内部 | children_lost 具体阈值仍待补。 |
| ending.tag.labor.group | Ending / Tag | 内部标签组 | overtime_used、long_shift_city、overwork_harm。 | Patch 009-2 | 工时标签 | 已封存原文 | 系统内部 | 一次加班日不进入终局审判。 |
| ending.tag.death_handling.group | Ending / Tag | 内部标签组 | cemetery_city、respectful_dead、cold_pit_city、body_medical_use、ash_fertilizer、unattended_dead。 | Patch 009-2 | 死亡处理标签 | 已封存原文 | 系统内部 | 记录城市如何面对死者。 |
| ending.tag.ration.group | Ending / Tag | 内部标签组 | ration_gruel、ration_soup、emergency_rations、ration_harm、normal_meals_maintained。 | Patch 009-2 | 食物配给标签 | 已封存原文 | 系统内部 | 普通配给摘要不重复显示。 |
| ending.tag.medical_policy.group | Ending / Tag | 内部标签组 | formal_medicine、stable_treatment、radical_treatment、expanded_care、medical_rations_used、triage_used、triage_cost、care_home_built、disabled_neglected。 | Patch 009-2 | 医疗处置标签 | 已封存原文 | 系统内部 | 养护所是正式建筑；该标签不涉及守炉堂 / 巡查所口径。 |
| ending.tag.entertainment.group | Ending / Tag | 内部标签组 | public_gathering、tavern_city、casino_city、bathhouse_relief、sedation_city。 | Patch 009-2 | 娱乐 / 减压标签 | 已封存原文 | 系统内部 | 娱乐不能洗白重大危机。 |
| ending.tag.oath_route.group | Ending / Tag | 内部标签组 | oath_route_started、oath_hall_enabled_running、mourning_bell、ember_register、shared_meal_oath、stay_oath、final_oath、oath_carried_zero_trust。 | Patch 009-2；全局总控 | 誓言路线标签 | 用户确认覆盖项 | 系统内部 | oath_hall_enabled_running 替代旧 oath_hall_built；守炉堂不是普通建筑。 |
| ending.tag.iron_route.group | Ending / Tag | 内部标签组 | iron_route_started、patrol_office_enabled_running、morning_rollcall、unified_notice、detention_used、census_control、final_decree、decree_carried_panic。 | Patch 009-2；全局总控 | 铁腕路线标签 | 用户确认覆盖项 | 系统内部 | patrol_office_enabled_running 替代旧 patrol_office_built；巡查所不是普通建筑。 |
| ending.tag.route_tendency.group | Ending / Tag | 内部标签组 | no_social_route、weak_oath、weak_iron、oath_governance、iron_governance、final_oath、final_decree、route_incomplete。 | Patch 009-2；全局总控 | 路线倾向 | 用户确认覆盖项 | 系统内部 | route_incomplete 指对应路线承接物未启用或未满足值守、路线长期未运行，不使用“核心建筑停工”。 |
| ending.tag.old_city.group | Ending / Tag | 内部标签组 | old_city_inactive、old_city_stabilized、old_city_persuaded、old_city_suppressed、old_city_departed、old_city_unresolved。 | Patch 009-2 / 第七批补表 | 旧城派标签 | 已封存原文 | 系统内部 | 旧城派不是誓言 / 铁腕路线本体。 |
| ending.tag.arrival.group | Ending / Tag | 内部标签组 | opened_gates、selective_refuge、closed_gates、refugee_pressure、refused_many。 | Patch 009-2 / 第七批补表 | 固定增员标签 | 已封存原文 | 系统内部 | 只记录多次选择或长期后果。 |
| ending.tag.promise.group | Ending / Tag | 内部标签组 | promise_keeper、promise_breaker、medical_promise_failed、food_promise_failed、children_promise_failed、old_city_promise_failed。 | Patch 009-2 / 第七批补表 | 承诺标签 | 已封存原文 | 系统内部 | 一次普通承诺失败且无长期后果，不进入主报告。 |
| ending.tag.frost.group | Ending / Tag | 内部标签组 | prepared_for_frost、unprepared_frost、last_night_ignored、frost_survived_clean、frost_survived_broken。 | Patch 009-2 / 第七批补表 | 第七霜落标签 | 已封存原文 | 系统内部 | 预警本身不直接失败。 |
  
   
⸻  
   
## 14_EndingFilter / 标签筛选、合并与文案选择  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------- | --------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------- | ----------- | --------- | ----- | ---- | ----------------------- |
| ending.severity.minor | Ending / Filter | 严重度 | minor | Patch 009-2 | 标签严重度 | 已封存原文 | 系统内部 | 不进入终局主报告。 |
| ending.severity.notable | Ending / Filter | 严重度 | notable | Patch 009-2 | 标签严重度 | 已封存原文 | 系统内部 | 默认留在详情页、内部记录或 009-C 候选。 |
| ending.severity.major | Ending / Filter | 严重度 | major | Patch 009-2 | 标签严重度 | 已封存原文 | 系统内部 | 默认进入终局报告候选。 |
| ending.severity.defining | Ending / Filter | 严重度 | defining | Patch 009-2 | 标签严重度 | 已封存原文 | 系统内部 | 优先于 major。 |
| ending.filter.default_rule | Ending / Filter | 内部规则 | 默认只有 major / defining 标签进入终局报告候选。 | Patch 009-2 | 标签严重度 | 已封存原文 | 系统内部 | 系统硬失败优先于所有普通标签。 |
| ending.filter.medical_merge | Ending / Filter | 合并规则 | 同时存在 medical_collapse、silent_hospital、medical_promise_failed、triage_cost 时，优先保留 silent_hospital；若没有，则保留 medical_collapse。 | Patch 009-2 | 医疗合并 | 已封存原文 | 系统内部 |  |
| ending.filter.food_merge | Ending / Filter | 合并规则 | 同时存在 famine_survivor、famine_city、food_promise_failed、ration_harm 时，优先保留 famine_city；若没有，则保留 famine_survivor。 | Patch 009-2 | 食物合并 | 已封存原文 | 系统内部 |  |
| ending.filter.cold_merge | Ending / Filter | 合并规则 | 同时存在 cold_houses、frozen_homeless、cold_engine 时，优先保留 frozen_homeless；否则 cold_engine 优先于 cold_houses。 | Patch 009-2 | 寒冷合并 | 已封存原文 | 系统内部 |  |
| ending.filter.death_merge | Ending / Filter | 合并规则 | 同时存在 mass_death、grave_city、unattended_dead 时，优先保留 grave_city；若没有，则保留 mass_death。 | Patch 009-2 | 死亡合并 | 已封存原文 | 系统内部 |  |
| ending.filter.society_merge | Ending / Filter | 合并规则 | oath_carried_zero_trust / decree_carried_panic > old_city_departed > broken_society。定义性标签可全部保留给 009-C，但 009-1 附加句最多显示其中 1 条。 | Patch 009-2 | 社会状态合并 | 已封存原文 | 系统内部 |  |
| ending.additional.count_rule | Ending / Filter | 数量规则 | 高质量胜利 0～1 条；标准胜利 1～2 条；惨胜 2 条；崩坏幸存 2～3 条；残火未灭 3 条；硬失败 0～1 条；玩家主动结束 0～1 条。 | Patch 009-2 | 附加句选择规则 | 已封存原文 | 系统内部 | 总上限 3 条。 |
| ending.additional.priority | Ending / Filter | 优先级 | hard_fail 原因 > defining 标签 > major 标签 > 与主文案不同主题的标签。 | Patch 009-2 | 附加句选择规则 | 已封存原文 | 系统内部 | 避免同类伤害重复。 |
| ending.interrogation.count_rule | Ending / Filter | 数量规则 | 终局报告默认显示 1 条执政官拷问文案。 | Patch 009-2 | 拷问选择规则 | 已封存原文 | 系统内部 | 硬失败可省略完整拷问，仅保留收束。 |
| ending.pool.random_rule | Ending / Filter | 随机规则 | 先按终局状态和标签筛选文案池，再在池内受控随机选择；若暂不实现随机，使用第一条或按本局种子固定选择。 | Patch 009-2 | 随机与权重 | 已封存原文 | 系统内部 | 不得跨状态完全随机。 |
| ending.report.length_rule | Ending / Filter | 长度规则 | 主文案 1 段；叙事式报告 1～2 段；重大状态附加句 0～3 条；重大炉律 / 路线痕迹摘要 0～2 条；拷问文案 1 条；隐藏成就记录 0～若干名称。 | Patch 009-2 | 长度控制 | 已封存原文 | 系统内部 | 不得把终局页写成调试日志或标签列表。 |
  
   
⸻  
   
## 15_InternalScoring / D55 结算与六大系统评分  
**15.1 D55 end_day 终局结算顺序**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------- | ----------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | ---------------- | ---- | ----------------------- |
| ending.d55.flow | Ending / Internal | 结算顺序 | 1. 锁定玩家输入。\\n2. 结算炉心、煤炭、overload、woodfuel、heat。\\n3. 结算建筑有效温度。\\n4. 结算生产与停工。\\n5. 结算食物消耗、饥饿、生食风险。\\n6. 结算医疗、疾病恶化、重症、伤残、死亡。\\n7. 结算寒冷暴露与寒冷死亡。\\n8. 结算信任 / 恐慌。\\n9. 检查硬失败条件。\\n10. 若未硬失败，进入六大系统终局评分。\\n11. 生成终局状态。\\n12. 生成 008 终局结果标签。\\n13. 提交 009 终局报告接口。\\n14. 写入 end_day 自动保存。\\n15. 显示终局报告入口。 | 第七批补表 | D55 终局结算流程 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 若过程中触发硬失败，不再进入普通存活质量评级。 |
  
**15.2 六大系统详细评分阈值**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ----------------------------------------- | -------------- | ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | --------- | ---------------- | ---- | ------------------------- |
| ending.score.coal_core.internal | Ending / Score | 内部评分 | 充足 4：无炉心关闭日、无煤炭缺口日、供暖不足日不超过 1、无红线日、D55 仍有煤且压力低于 70。\\n稳定 3：无炉心关闭日、煤炭缺口日不超过 1、供暖不足日不超过 2、红线日不超过 1、压力低于 85。\\n勉强 2：炉心关闭日不超过 1、煤炭缺口日不超过 3、供暖不足日不超过 4、压力低于 95。\\n不足 1：炉心关闭日不超过 2，或煤炭缺口日不超过 5，或压力达到 95 以上，但未崩毁。\\n崩坏 0：炉心关闭至少 3 天、煤炭缺口至少 6 天或多日红线运行，但未触发炉心崩毁。 | 第七批补表 | 煤炭 / 炉心评分 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 炉心崩毁直接 hard_fail。 |
| ending.score.food.internal | Ending / Score | 内部评分 | 充足 4：无饥饿日、食物不足日不超过 1、D55 可食用库存不少于 2 天。\\n稳定 3：无饥饿日、食物不足日不超过 2、D55 可食用库存不少于 1 天。\\n勉强 2：饥饿日不超过 1、食物不足日不超过 4、无饥饿死亡。\\n不足 1：饥饿日不超过 3、食物不足日不超过 6，或出现少量饥饿死亡，但人口未归零。\\n崩坏 0：饥饿日至少 4、长期饥荒或饥饿死亡显著扩大，但仍有人存活。 | 第七批补表 | 食物评分 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 食物崩坏不单独 hard_fail。 |
| ending.score.housing_temperature.internal | Ending / Score | 内部评分 | 充足 4：住房覆盖率 100%、无住所为 0、寒屋日不超过 1、无寒冷死亡、关键建筑无低温停工。\\n稳定 3：住房覆盖率至少 95%、无住所不超过 5、寒屋日不超过 2、无寒冷死亡。\\n勉强 2：住房覆盖率至少 80%、无住所不超过 20、寒屋日不超过 4、寒冷死亡日不超过 1。\\n不足 1：住房覆盖率至少 60%，或无住所不超过 40，或多日寒屋 / 无住所暴露，但仍有人存活。\\n崩坏 0：无住所超过 40、寒屋日至少 5、寒冷死亡日至少 2，或关键建筑长期低温停工。 | 第七批补表 | 住房 / 温度评分 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| ending.score.medical_disease.internal | Ending / Score | 内部评分 | 充足 4：医疗覆盖率至少 100%、重症率不超过 5%、医疗溢出日不超过 1、无疾病死亡。\\n稳定 3：医疗覆盖率至少 80%、重症率不超过 10%、医疗溢出日不超过 2。\\n勉强 2：医疗覆盖率至少 50%、重症率不超过 18%、医疗崩溃日不超过 1。\\n不足 1：医疗覆盖率低于 50%，或重症率超过 18%，或医疗崩溃日不超过 3，但仍有人存活。\\n崩坏 0：医疗崩溃日至少 4、所有医疗建筑长期停治，或病患大量积压并持续死亡。 | 第七批补表 | 医疗 / 疾病评分 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| ending.score.trust_panic.internal | Ending / Score | 内部评分 | 充足 4：信任至少 70、恐慌不超过 30、无信任 / 恐慌危机日、旧城派未出走。\\n稳定 3：信任至少 50、恐慌不超过 50、两类危机日均不超过 1。\\n勉强 2：信任至少 30、恐慌不超过 75、两类危机日均不超过 3。\\n不足 1：信任大于 0、恐慌低于 100，或由路线终章勉强承接危机，但社会明显破裂。\\n崩坏 0：信任归零且被终火誓约承接；或恐慌达到 100 且被最高戒令压制；或旧城派出走且社会系统严重破裂。 | 第七批补表 | 信任 / 恐慌评分 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 若终章炉律承接失败轴，本系统最高不得超过 1 分。 |
| ending.score.population_death.internal | Ending / Score | 内部评分 | 充足 4：第七霜落存活率至少 90%、无大量死亡日、D55 存活人口至少为城市连续性参考线的 2 倍。\\n稳定 3：存活率至少 75%、大量死亡日不超过 1、D55 存活人口不低于连续性参考线。\\n勉强 2：存活率至少 55%，且不低于连续性参考线。\\n不足 1：D55 仍有人存活，但低于连续性参考线，或存活率低于 55%。\\n崩坏 0：存活率低于 35%，或存活人口低于连续性参考线的 60%，但仍有人活过第七霜落。 | 第七批补表 | 人口 / 死亡评分 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 存活人口归零直接 hard_fail。 |
  
**15.3 总分分档与高质量胜利限制**  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ----------------------------- | -------------- | ---- | ------------------------------------------------------------------------------------------------------- | ------------------- | --------- | ------- | ---- | ----------------------------------------------------------------------------------------- |
| ending.score.band.high | Ending / Score | 分档 | 20～24：高质量胜利 | Patch 008-4 / 第七批补表 | 终局状态分档 | 已封存原文 | 系统内部 |  |
| ending.score.band.standard | Ending / Score | 分档 | 15～19：标准胜利 | Patch 008-4 / 第七批补表 | 终局状态分档 | 已封存原文 | 系统内部 |  |
| ending.score.band.bitter | Ending / Score | 分档 | 10～14：惨胜 | Patch 008-4 / 第七批补表 | 终局状态分档 | 已封存原文 | 系统内部 |  |
| ending.score.band.collapse | Ending / Score | 分档 | 5～9：崩坏幸存 | Patch 008-4 / 第七批补表 | 终局状态分档 | 已封存原文 | 系统内部 |  |
| ending.score.band.ember | Ending / Score | 分档 | 0～4：残火未灭 | Patch 008-4 / 第七批补表 | 终局状态分档 | 已封存原文 | 系统内部 |  |
| ending.score.high_victory_cap | Ending / Score | 限制规则 | 任一系统崩坏、总死亡比例超过 20% 或信任 / 恐慌崩坏时，最高为标准胜利；煤炭 / 炉心或人口 / 死亡不足或崩坏时，最高为惨胜；崩坏项至少 3 项时最高为崩坏幸存；崩坏项至少 5 项时最高为残火未灭。 | Patch 008-4 / 第七批补表 | 高质量胜利限制 | 用户确认覆盖项 | 系统内部 | 若同时命中多个结局上限，始终取最严格、最低的结果上限。例如煤炭 / 炉心崩坏同时命中“最高标准胜利”和“最高惨胜”时，应采用更严格的“最高惨胜”，避免因判断顺序不同得到不同结局。 |
  
   
⸻  
   
## 16_FrostInterface / 第七霜落准备与终局接口标签  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------------- | --------------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | --------------------- | ---------------- | ---- | --------------------- |
| ending.tag.prepared_for_frost.rule | Ending / Tag | 内部条件 | 进入第七霜落时，煤炭、食物、住房、医疗、信任、恐慌、旧城派和关键终局科技八项中至少满足五项准备条件。 | 第七批补表 | prepared_for_frost | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 具体八项阈值按第七批补表。 |
| ending.tag.unprepared_frost.rule | Ending / Tag | 内部条件 | 进入第七霜落时，煤炭不足、食物不足、存在无住所、医疗缺口、低信任、高恐慌、旧城派高风险或炉心高压八项中至少满足三项。 | 第七批补表 | unprepared_frost | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| ending.tag.frost_survived_clean.rule | Ending / Tag | 内部条件 | D55 存活、六大系统无崩坏、最多一项不足、第七霜落期间无大量死亡日，且未触发 hard_fail。 | 第七批补表 | frost_survived_clean | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| ending.tag.frost_survived_broken.rule | Ending / Tag | 内部条件 | D55 存活且未触发 hard_fail，并满足以下任一条件时，可提交 frost_survived_broken：\\n1. 至少两项系统崩坏；\\n2. 六大系统总分不超过 9；\\n3. 触发 city_continuity_broken；\\n4. 第七霜落期间存在大量死亡日，并且至少两个系统评级为不足或崩坏。 | 第七批补表；用户补充校正 | frost_survived_broken | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 以上条件为“任一满足”，不是全部同时满足。 |
| ending.tag.oath_carried_zero_trust.rule | Ending / Route | 内部条件 | 信任归零、终火誓约已生效且未触发其他硬失败时，不触发 trust_exile；信任 / 恐慌系统最高 1 分，并提交 oath_carried_zero_trust。 | 第七批补表 | 终火誓约接口 | 用户确认覆盖项 | 系统内部 | 终火誓约不提高信任，也不免疫其他硬失败。 |
| ending.tag.decree_carried_panic.rule | Ending / Route | 内部条件 | 恐慌达到 100、最高戒令已生效且未触发其他硬失败时，不触发 panic_expelled；信任 / 恐慌系统最高 1 分，并提交 decree_carried_panic。 | 第七批补表 | 最高戒令接口 | 用户确认覆盖项 | 系统内部 | 最高戒令不降低恐慌，也不免疫其他硬失败。 |
| ending.tag.old_city_result.rule | Ending / OldCity | 内部条件 | 旧城派散去提交 old_city_stabilized；部分出走或大规模出走提交 old_city_departed；誓言接口显著劝留可提交 old_city_persuaded；铁腕接口显著压低可提交 old_city_suppressed；终局前未妥善解决则提交 old_city_unresolved。 | 第七批补表 | 旧城派接口 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 出走不是死亡。 |
| ending.tag.arrival_result.rule | Ending / FixedArrival | 内部条件 | 三次固定增员中至少两次全部接纳提交 opened_gates；至少两次拒绝提交 closed_gates；固定增员后五天内住房、食物、医疗任一系统至少三天不足，可提交 refugee_pressure。 | 第七批补表 | 固定增员接口 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 单次选择不必然进入终局审判。 |
| ending.tag.promise_result.rule | Ending / Promise | 内部条件 | 关键承诺成功至少四次且无严重 / 临界承诺失败，可提交 promise_keeper；承诺失败至少三次或严重 / 临界失败至少两次，可提交 promise_breaker；旧城派承诺失败并推动危机升级，可提交 old_city_promise_failed。 | 第七批补表 | 承诺接口 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
  
   
⸻  
   
## 17_HiddenAchievement / 隐藏成就终局显示  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------- | -------------------- | ----- | -------------------------------------------------------- | ----------- | --------- | ----- | ---- | ------------------ |
| ending.hidden_achievement.label | Ending / Achievement | UI 标签 | 隐藏成就：{achievement_name} | Patch 009-2 | 隐藏成就终局显示 | 已封存原文 | 玩家可见 |  |
| ending.hidden_achievement.record | Ending / Achievement | 终局记录 | 额外记录：本局已解锁隐藏成就「{achievement_name}」。 | Patch 009-2 | 隐藏成就终局显示 | 已封存原文 | 玩家可见 | 两种显示格式择一。 |
| ending.hidden_achievement.rule | Ending / Achievement | 内部规则 | 终局报告只记录已解锁隐藏成就名称，不显示完整友情备注，不进入主审判，不参与胜利评分、硬失败、路线倾向或拷问筛选。 | Patch 009-2 | 隐藏成就规则 | 已封存原文 | 系统内部 | 隐藏成就名称不计入路线痕迹摘要上限。 |
  
   
⸻  
   
## 18_TODO_TEXT / 第 6 轮未封存内容  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------------- | -------------------- | ------------- | ----------- | --------------------------- | ------------- | --------- | ----------- | ---------------------------------------------------------- |
| ending.report.death_record_sentence | Ending / Report | 死亡记录动态句 | TODO_TEXT | Patch 009-1；用户补充校正 | 叙事式炉城报告 | TODO_TEXT | 玩家可见（运行时模板） | 必须根据本局实际死亡处理方式选择；墓园、冷藏坑、余烬名册不得以斜杠形式直接显示。若没有已封存的对应句，不得自行创作。 |
| ending.route.final_oath.full_text | Ending / Route | 终火誓约专属完整结局文案 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 | 009-C 未提供，不得自行补写。 |
| ending.route.final_decree.full_text | Ending / Route | 最高戒令专属完整结局文案 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 | 009-C 未提供，不得自行补写。 |
| ending.route.oath.full_text | Ending / Route | 誓言路线完整总结 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 | 当前仅保留一句式路线痕迹。 |
| ending.route.iron.full_text | Ending / Route | 铁腕路线完整总结 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 | 当前仅保留一句式路线痕迹。 |
| ending.old_city.full_text | Ending / OldCity | 旧城派完整结局文案 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 | 当前仅保留一句式痕迹和内部标签。 |
| ending.children.full_text | Ending / Institution | 儿童路线完整结局文案 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 |  |
| ending.death_handling.full_text | Ending / Institution | 死亡处理完整结局文案 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 |  |
| ending.entertainment.full_text | Ending / Institution | 娱乐 / 赌场完整结局文案 | TODO_TEXT | Patch 009-1 / 009-2 | 009-C 接口 | TODO_TEXT | 玩家可见 |  |
| ending.tag.children_lost.threshold | Ending / Tag | 儿童死亡阈值 | TODO_VALUE | Patch 009-2 | children_lost | TODO | 系统内部 | 具体阈值未封存，不得猜测。 |
| ending.ui.detail_page | Ending / UI | 终局档案详情页 | TODO_TEXT | Patch 008-4 / 009-1 / 009-2 | UI 接口 | TODO_TEXT | 待判定 | 是否显示完整六大系统数值表尚未封存。 |
| ending.pool.random_weight | Ending / Internal | 文案随机权重 | TODO_VALUE | Patch 009-2 | 随机与权重 | TODO | 系统内部 | 未封存；可先使用池内第一条或本局种子固定选择。 |
| ending.after_day55.continue_simulation | Ending / Postgame | 第 56 天后完整继续模拟 | TODO_SYSTEM | Patch 008-4 | D55 后接口 | 后置 | 系统内部 | 不在 V1 当前代码窗实现。 |
  
   
⸻  
   
## 19_Deprecated / 作废旧口径  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------------------- | ---------- | ------- | ------------------------------------ | ------------------- | --------- | ----- | -------------------------------- | ------------------------------------------- |
| deprecated.ending.terminal_fail | Deprecated | 旧终局标签 | terminal_fail | Patch 008-4 / 第七批补表 | 作废旧口径 | 作废旧口径 | 系统内部 | 低质量存活使用 collapse_survival 或 ember_survival。 |
| deprecated.ending.low_score_hard_fail | Deprecated | 旧机制口径 | 低综合分直接失败 | Patch 008-4 | 作废旧口径 | 作废旧口径 | 系统内部 | 六大系统低分进入存活质量评级，不新增硬失败。 |
| deprecated.ending.multi_collapse_hard_fail | Deprecated | 旧机制口径 | 多系统崩坏直接失败 | Patch 008-4 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.ending.continuity_hard_fail | Deprecated | 旧机制口径 | 低于城市连续性参考线直接失败 | Patch 008-4 | 作废旧口径 | 作废旧口径 | 系统内部 | 仅提交城市连续性崩坏标签。 |
| deprecated.ending.frost_score_hard_fail | Deprecated | 旧机制口径 | 第七霜落终局验收低分直接失败 | Patch 008-4 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.ending.collapse_survival_fail | Deprecated | 旧结果口径 | 崩坏幸存是失败 | Patch 008-4 / 009-1 | 作废旧口径 | 作废旧口径 | 系统内部 | 崩坏幸存属于存活结局。 |
| deprecated.ending.ember_survival_fail | Deprecated | 旧结果口径 | 残火未灭是失败 | Patch 008-4 / 009-1 | 作废旧口径 | 作废旧口径 | 系统内部 | 残火未灭属于存活结局。 |
| deprecated.ending.player_ended_hard_fail | Deprecated | 旧结果口径 | 玩家主动结束属于系统硬失败 | Patch 008-4 / 009-1 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式标签为 player_ended。 |
| deprecated.ending.trust_fail_field | Deprecated | 旧字段 | trust_fail | Patch 009-1 / 009-2 | 作废旧字段 | 作废旧口径 | 系统内部 | 正式硬失败类型使用 trust_exile。 |
| deprecated.ending.panic_fail_field | Deprecated | 旧字段 | panic_fail | Patch 009-1 / 009-2 | 作废旧字段 | 作废旧口径 | 系统内部 | 正式硬失败类型使用 panic_expelled。 |
| deprecated.ending.trust_city_destroyed | Deprecated | 旧叙事口径 | 信任失败等于炉城立即毁灭 | Patch 009-1 / 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 信任失败为执政官被流放。 |
| deprecated.ending.panic_city_destroyed | Deprecated | 旧叙事口径 | 恐慌失败等于炉城立即毁灭 | Patch 009-1 / 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 恐慌失败为执政官被驱逐。 |
| deprecated.ending.panic_old_city_mix | Deprecated | 旧文案口径 | 通用恐慌失败文案混入南方传言 / 旧城派 | Patch 009-1 / 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 仅明确触发旧城派标签时，后续专属文案才可写旧城派。 |
| deprecated.ending.default_numeric_table | Deprecated | 旧 UI 口径 | 终局主报告默认展示大段数值摘要表 | Patch 009-1 / 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 默认使用叙事式炉城报告。 |
| deprecated.ending.backend_date_in_main_text | Deprecated | 旧显示口径 | 玩家主文案大量使用 D49 / D55 / D49～D55 | Patch 009-1 | 作废旧口径 | 作废旧口径 | 系统内部 | 玩家可见文案使用自然中文日期。 |
| deprecated.ending.hope_state | Deprecated | 旧状态字段 | hope_state / 希望状态 | Patch 009-1 / 全局口径 | 作废旧口径 | 系统内部 | “希望 / 未来 / 春天”只作为文学表达，不作为独立状态字段。 |  |
| deprecated.ending.small_event_judgment | Deprecated | 旧筛选口径 | 一次死亡、一次露宿、一次 heat、短暂食物不足或轻微医疗缺口进入主审判 | Patch 009-1 / 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 小事只进入日志、日结或详情页。 |
| deprecated.ending.hidden_achievement_judgment | Deprecated | 旧筛选口径 | 隐藏成就进入主审判、参与评分或触发拷问 | Patch 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 终局仅记录名称。 |
| deprecated.ending.route_overrides_result | Deprecated | 旧路线口径 | 誓言 / 铁腕路线标签覆盖硬失败或洗白系统崩坏 | Patch 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 路线只影响社会解释、附加句、拷问倾向和 009-C 接口。 |
| deprecated.route.oath_hall_built_tag | Deprecated | 旧路线标签 | oath_hall_built / 守炉堂建成并运行 | Patch 009-2；全局总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式按“守炉堂已启用并运行”；守炉堂不是普通建筑。 |
| deprecated.route.patrol_office_built_tag | Deprecated | 旧路线标签 | patrol_office_built / 巡查所建成并运行 | Patch 009-2；全局总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式按“巡查所已启用并运行”；巡查所不是普通建筑。 |
| deprecated.route.core_building_shutdown | Deprecated | 旧路线倾向口径 | 路线核心建筑长期停工 | Patch 009-2；全局总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式读取路线承接物是否启用、是否满足值守、路线是否运行。 |
| deprecated.ending.009b_r1_r2_summary | Deprecated | 旧摘要口径 | 009-B r1 全部细分儿童分支；r2 普通医疗、食物配给、工时摘要句 | Patch 009-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 以 009-B r3 收敛口径为准。 |
| deprecated.ending.full_postgame_v1 | Deprecated | 旧后日谈口径 | 第 55 天后自动进入完整继续模拟、完整后日谈或第 56 天新经营循环 | Patch 008-4 | 作废旧口径 | 作废旧口径 | 系统内部 | 当前只实现终局报告、结果标签和主动结束接口。 |
  
   
⸻  
   
本轮已审：  
1. 第七霜落温度表、每日状态、D55 结算、六大系统评分与结局分档已全部收入。  
2. 12 条暂定评分 / 标签条件统一使用“代码窗暂定实现值 / 测试窗必测”，不再保留同义状态名。  
3. 建筑有效温度公式已改为修正类别，不再把“炉心功率稳定 I”写成已确定独立加法项。  
4. 六大系统总分模板使用 {total_score}，不再使用字母 X 作为运行时变量。  
5. 叙事式终局报告模板已标为“玩家可见（运行时模板）”；死亡记录改用 {death_record_sentence}，不得把墓园 / 冷藏坑 / 余烬名册斜杠原样显示。  
6. 人口归零、炉心崩毁与恐慌失败文案池已补日期筛选条件，不改封存正文。  
7. frost_survived_broken 已明确为任一条件满足，不要求全部条件同时命中。  
8. 多项结局上限同时命中时，统一采用最严格、最低的结果上限。  
9. 娱乐痕迹中的正式建筑名已统一为“小酒馆”。  
10. 誓言 / 铁腕路线痕迹必须依据本局实际签署和使用的炉律生成，不得声称玩家实施过未签署内容。  
11. 系统硬失败只保留人口归零、炉心崩毁、信任归零未被承接、恐慌达到 100 未被压制四项。  
12. 崩坏幸存、残火未灭和玩家主动结束均未误写为 hard_fail。  
13. 信任失败统一为“执政官被流放”，恐慌失败统一为“执政官被驱逐”；没有把炉城写成必然当场灭亡。  
14. 终局报告采用标题、主文案、叙事式炉城报告、重大状态附加句、重大炉律 / 路线痕迹、执政官拷问和隐藏成就名称记录，不默认展示大段数值表。  
15. hope_state 未回流；“希望 / 未来 / 春天”只保留为文学表达。  
16. 守炉堂 / 巡查所已按路线承接物“自动启用并运行”校正；旧 oath_hall_built、patrol_office_built 与“核心建筑停工”只保留在 Deprecated。  
17. 009-C 路线专属完整长文案、儿童死亡阈值、随机权重和第 56 天后继续模拟均保持 TODO / 后置，没有擅自补写。  
18. 第 6 轮为最后一轮正文；后续只做六轮总审，不再新增第 7 轮正文。  
