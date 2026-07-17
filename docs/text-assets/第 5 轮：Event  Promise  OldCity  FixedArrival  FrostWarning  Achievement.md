# 第 5 轮：Event / Promise / OldCity / FixedArrival / FrostWarning / Achievement  
**全局导入说明：**凡可见性标记为“系统内部”的条目，默认属于开发注释、配置说明或测试口径，不进入 runtime 文案库；其 text_id 仅作为文档索引键。只有明确标记为“玩家可见”或“通用”的文案资产才进入正式 TextRegistry。  
## 01_Event / 事件通用显示与系统提示  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------------- | --------------- | ----- | ------------------------------- | ------------------- | ------------ | --------- | ---- | ------------------------------------ |
| event.ui.title.label | Event / UI | UI 标签 | 事件标题 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.type.label | Event / UI | UI 标签 | 事件类型 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.trigger.label | Event / UI | UI 标签 | 触发原因 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.status_summary.label | Event / UI | UI 标签 | 当前状态摘要 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.options.label | Event / UI | UI 标签 | 可选选项 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.unavailable_actions.label | Event / UI | UI 标签 | 当前不可用的额外手段 | Patch 007-1 | 可用 / 不可用选项规则 | 已封存原文 | 玩家可见 | 不可用手段不进入正式 A / B / C。 |
| event.ui.immediate_effect.label | Event / UI | UI 标签 | 即时后果方向 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.promise_hint.label | Event / UI | UI 标签 | 承诺任务提示 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.ui.requirement_limit.label | Event / UI | UI 标签 | 冷却或前置限制 | Patch 007-1 | 事件显示格式 | 已封存原文 | 通用 |  |
| event.option.unavailable.feedback | Event / Failure | 失败提示 | TODO_TEXT | Patch 007-1 | 可用 / 不可用选项规则 | TODO_TEXT | 待判定 | 只封存“返回具体失败原因”的规则；通用失败提示正文未封存，不得自行补写。 |
| event.option.unavailable.no_change | Event | 内部规则 | 不改变状态，不结算效果，不结算代价，不消耗冷却，不生成承诺。 | Patch 007-1 | 可用 / 不可用选项规则 | 已封存原文 | 系统内部 |  |
| event.extra.shared_meal.unavailable | Event / Route | 不可用提示 | 共食誓餐：需要守炉堂已启用并运行，且熟食足够。 | Patch 007-1；全局总控 | 不可用额外手段示例 | 用户确认覆盖项 | 玩家可见 | 已将旧“建成”口径改为“已启用并运行”。 |
| event.extra.registry_review.unavailable | Event / Route | 不可用提示 | 登记审查：需要旧城派危机已激活，且巡查所已启用并运行。 | Patch 007-1；全局总控 | 不可用额外手段示例 | 用户确认覆盖项 | 玩家可见 | 巡查所不是普通建筑，不进入 build。 |
| event.rule.no_auto_command | Event | 内部规则 | 事件负责让问题被看见，命令负责真正改变城市运行状态。 | Patch 007-1 | 事件与核心命令边界 | 已封存原文 | 系统内部 | 事件不得永久自动执行核心命令。 |
| event.rule.suppressed_no_hidden_result | Event | 内部规则 | 被压下的事件不弹完整事件，不结算选项后果，也不替玩家偷偷选择。 | Patch 007-1 / 007-3 | 事件被压下后的处理 | 已封存原文 | 系统内部 |  |
  
   
⸻  
   
## 02_Promise / 承诺任务显示与通用口径  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ----------------------------------- | ------------------ | ----- | -------------------------------------- | --------------------- | ----------- | ---------------- | ---- | -------------------------------- |
| promise.system.name | Promise | 系统名 | 承诺任务 | Patch 007-1 / 007-3 | 承诺任务基础规则 | 已封存原文 | 通用 |  |
| promise.goal.label | Promise / UI | UI 标签 | 承诺目标 | Patch 007-3 | 承诺目标显示规则 | 已封存原文 | 通用 |  |
| promise.deadline.label | Promise / UI | UI 标签 | 截止日 | Patch 007-3 | 承诺目标显示规则 | 已封存原文 | 通用 |  |
| promise.success_direction.label | Promise / UI | UI 标签 | 成功方向 | Patch 007-3 | 承诺目标显示规则 | 已封存原文 | 通用 |  |
| promise.failure_direction.label | Promise / UI | UI 标签 | 失败方向 | Patch 007-3 | 承诺目标显示规则 | 已封存原文 | 通用 |  |
| promise.active_count.label | Promise / UI | UI 标签 | 当前已有承诺数量 | Patch 007-3 | 承诺目标显示规则 | 已封存原文 | 通用 |  |
| promise.same_type_exists.label | Promise / UI | UI 标签 | 同类承诺是否已存在 | Patch 007-3 | 承诺目标显示规则 | 已封存原文 | 通用 |  |
| promise.slot.full | Promise / Failure | 不可用提示 | 当前承诺任务已满。 | Patch 007-3 | 承诺任务上限 | 已封存原文 | 玩家可见 | 同时最多 2 个 active 承诺。 |
| promise.same_type.active | Promise / Failure | 不可用提示 | TODO_TEXT | Patch 007-3 | 承诺任务上限 | TODO_TEXT | 待判定 | 同类承诺上限规则已封存，但完整玩家提示未单独封存，不得自行补写。 |
| promise.example.food.title | Promise | 承诺名 | 承诺补足口粮 | Patch 007-3 | 承诺目标显示示例 | 已封存原文 | 玩家可见 |  |
| promise.example.food.goal | Promise | 目标提示 | 目标：第 X 天结束前，让熟食储备达到安全线。 | Patch 007-3 | 承诺目标显示示例 | 用户确认覆盖项 | 玩家可见 | 原示例写第 23 天，正式资产改用变量 X，避免固定日期误用。 |
| promise.example.deadline | Promise | 截止提示 | 截止：第 X 天。 | Patch 007-3 | 承诺目标显示示例 | 用户确认覆盖项 | 玩家可见 | 使用动态日期。 |
| promise.example.success | Promise | 成功方向 | 成功：信任上升，恐慌下降。 | Patch 007-3 | 承诺目标显示示例 | 已封存原文 | 玩家可见 |  |
| promise.example.failure | Promise | 失败方向 | 失败：信任下降，恐慌上升。 | Patch 007-3 | 承诺目标显示示例 | 已封存原文 | 玩家可见 |  |
| promise.success.title | Promise / Feedback | 结算标题 | TODO_TEXT | Patch 007-3 | 承诺成功规则 | TODO_TEXT | 玩家可见 | 成功效果已封存，完整标题未封存。 |
| promise.failure.title | Promise / Feedback | 结算标题 | TODO_TEXT | Patch 007-3 | 承诺失败规则 | TODO_TEXT | 玩家可见 | 失败效果已封存，完整标题未封存。 |
| promise.rule.not_buff | Promise | 内部规则 | 承诺只是“给我一点时间”，不是问题现在已经自行好转。 | Patch 007-3 | 承诺任务不是持续增益 | 已封存原文 | 系统内部 | 不暂停原有日结惩罚。 |
| promise.rule.deadline_day_available | Promise | 内部规则 | 截止日当天仍可完成目标，下一天开始时再检查成功或失败。 | Patch 007-3 / 第五批补表 | 承诺截止日 | 已封存原文 | 系统内部 |  |
| promise.rule.no_free_cancel | Promise | 内部规则 | 承诺任务开启后不能无代价取消；若提供取消功能，取消按主动放弃并立即失败结算。 | Patch 007-3 | 承诺任务不能无代价取消 | 已封存原文 | 系统内部 |  |
| promise.rule.max_active | Promise | 内部规则 | 同一时间最多存在 2 个 active 承诺任务。 | Patch 007-1 / 007-3 | 承诺任务上限 | 已封存原文 | 系统内部 |  |
| promise.rule.max_same_type | Promise | 内部规则 | 同一时间最多存在 1 个同类承诺任务。 | Patch 007-1 / 007-3 | 承诺任务上限 | 已封存原文 | 系统内部 |  |
| promise.rule.no_new_from_day49 | Promise | 内部规则 | 自第 49 天起，不再开启新的普通承诺任务。 | Patch 007-3 / 第七批干净补表 | 固定终局阶段承诺限制 | 用户确认覆盖项 | 系统内部 | 第 49～55 天为第七霜落固定终局阶段。 |
| promise.rule.deadline_cap_day48 | Promise | 内部规则 | 第 42 天后开启的普通承诺，截止日不得超过第 48 天。 | 第五批干净补表 | 终局前承诺期限收口 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 终局前承诺期限收口值，试玩后复核。 |
  
   
⸻  
   
## 03_Promise / 承诺类型名称  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------- | ------- | ----- | --------- | ----------- | --------- | ----- | --- | -- |
| promise.food.name | Promise | 承诺类型名 | 食物承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.medical.name | Promise | 承诺类型名 | 医疗承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.housing.name | Promise | 承诺类型名 | 住房承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.body.name | Promise | 承诺类型名 | 遗体处理承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.children.name | Promise | 承诺类型名 | 儿童安置承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.labor.name | Promise | 承诺类型名 | 工时 / 过劳承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.coal.name | Promise | 承诺类型名 | 煤炭承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.furnace.name | Promise | 承诺类型名 | 炉心压力承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.old_city.name | Promise | 承诺类型名 | 旧城派承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.trust.name | Promise | 承诺类型名 | 信任承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
| promise.panic.name | Promise | 承诺类型名 | 恐慌承诺 | Patch 007-3 | 承诺任务类型 | 已封存原文 | 通用 |  |
  
   
⸻  
   
## 04_Event / 基础民生危机事件正文  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------- | ---------------- | ---- | ----------------------------------------------------------------------------------- | ------------------ | ------------- | --------- | ---- | ------------------------------------------- |
| event.empty_pot.title | Event / Food | 事件标题 | 空锅请愿 | Patch 007-2 | 食物事件一 | 已封存原文 | 玩家可见 |  |
| event.empty_pot.body | Event / Food | 事件正文 | 食堂外有人举起空碗。\\n\\n他们没有闹事，只是站在那里。\\n碗底被刮得很干净，像一圈冻住的月亮。\\n\\n有人说：我们不是要更多，只是想知道明天还有没有。 | Patch 007-2 | 空锅请愿 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.empty_pot.option_a | Event / Food | 选项 | 承诺补足口粮 | Patch 007-2 | 空锅请愿 | 已封存原文 | 玩家可见 | 生成食物承诺。 |
| event.empty_pot.option_b | Event / Food | 选项 | 维持当前配给 | Patch 007-2 | 空锅请愿 | 已封存原文 | 玩家可见 |  |
| event.empty_pot.option_c | Event / Food | 选项 | 调整配给 | Patch 007-2 | 空锅请愿 | 用户确认覆盖项 | 玩家可见 | 原文为“提示调整配给 / 当日临时压低分配”；正式按钮取简短名，具体效果仍按系统规则。 |
| event.raw_food_dispute.title | Event / Food | 事件标题 | 生食争议 | Patch 007-2 | 食物事件二 | 已封存原文 | 玩家可见 |  |
| event.raw_food_dispute.body | Event / Food | 事件正文 | 有人在炉边啃半冻的生肉。\\n\\n孩子看着那块肉，没有说话。\\n大人也没有。\\n\\n第二天，医疗站多了几张发冷的脸。 | Patch 007-2 | 生食争议 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.raw_food_dispute.option_a | Event / Food | 选项 | 承诺恢复熟食供应 | Patch 007-2 | 生食争议 | 已封存原文 | 玩家可见 |  |
| event.raw_food_dispute.option_b | Event / Food | 选项 | 暂时允许继续食用生食 | Patch 007-2 | 生食争议 | 已封存原文 | 玩家可见 |  |
| event.raw_food_dispute.option_c | Event / Food | 选项 | 优先供应儿童熟食 | Patch 007-2 | 生食争议 | 已封存原文 | 玩家可见 | 需要儿童人数和熟食均大于 0。 |
| event.medical_beds_emergency.title | Event / Medical | 事件标题 | 病床告急 | Patch 007-2 | 医疗事件一 | 已封存原文 | 玩家可见 |  |
| event.medical_beds_emergency.body | Event / Medical | 事件正文 | 医疗站门口排着人。\\n\\n有人坐在雪里，有人靠着墙睡着。\\n医生没有抬头，只说了一句：\\n\\n下一个床位空出来之前，别再有人倒下了。 | Patch 007-2 | 病床告急 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.medical_beds_emergency.option_a | Event / Medical | 选项 | 承诺扩容医疗 | Patch 007-2 | 病床告急 | 已封存原文 | 玩家可见 |  |
| event.medical_beds_emergency.option_b | Event / Medical | 选项 | 临时腾挪床位 | Patch 007-2 | 病床告急 | 已封存原文 | 玩家可见 | 需要对应医疗炉律或扩容能力。 |
| event.medical_beds_emergency.option_c | Event / Medical | 选项 | 维持现状 | Patch 007-2 | 病床告急 | 已封存原文 | 玩家可见 |  |
| event.severe_case_backlog.title | Event / Medical | 事件标题 | 重症积压 | Patch 007-2 | 医疗事件二 | 已封存原文 | 玩家可见 |  |
| event.severe_case_backlog.body | Event / Medical | 事件正文 | 医疗站里安静得不正常。\\n\\n重症病人不再呻吟。\\n他们只是看着炉光，好像那是某种很远的东西。\\n\\n医生说：我们还能救一些人。\\n但不是所有人。 | Patch 007-2 | 重症积压 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.severe_case_backlog.option_a | Event / Medical | 选项 | 投入额外医疗配给 | Patch 007-2 | 重症积压 | 已封存原文 | 玩家可见 | 需要已解锁额外医疗配给。 |
| event.severe_case_backlog.option_b | Event / Medical | 选项 | 承诺扩大重症收治能力 | Patch 007-2 | 重症积压 | 已封存原文 | 玩家可见 |  |
| event.severe_case_backlog.option_c | Event / Medical | 选项 | 接受现状 | Patch 007-2 | 重症积压 | 已封存原文 | 玩家可见 |  |
| event.first_body.title | Event / Death | 事件标题 | 第一具遗体 | Patch 007-2 | 死亡事件一 | 已封存原文 | 玩家可见 |  |
| event.first_body.body | Event / Death | 事件正文 | 他们把那个人抬到炉边时，雪还粘在他的袖口上。\\n\\n没人知道该把他放在哪里。\\n也没人愿意第一个说：\\n\\n他已经不需要床位了。 | Patch 007-2 | 第一具遗体 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.first_body.option_a | Event / Death | 选项 | 公开悼念 | Patch 007-2 | 第一具遗体 | 已封存原文 | 玩家可见 |  |
| event.first_body.option_b | Event / Death | 选项 | 低调处理 | Patch 007-2 | 第一具遗体 | 已封存原文 | 玩家可见 |  |
| event.first_body.option_c | Event / Death | 选项 | 暂时搁置 | Patch 007-2 | 第一具遗体 | 已封存原文 | 玩家可见 |  |
| event.first_body.hint | Event / Death | 系统提示 | 死亡处理可通过社会适配炉律中的墓园 / 冷藏坑路线解决。若遗体长期未处理，将持续影响信任与恐慌。 | Patch 007-2；用户补充校正 | 第一具遗体 / 提示 | 用户确认覆盖项 | 玩家可见 | “社会适配城约”为旧表述，正式系统名称统一使用“社会适配炉律”。 |
| event.bodies_under_snow.title | Event / Death | 事件标题 | 雪下尸列 | Patch 007-2 | 死亡事件二 | 已封存原文 | 玩家可见 |  |
| event.bodies_under_snow.body | Event / Death | 事件正文 | 雪把遗体盖住了一半。\\n\\n这本来让他们看起来安静些。\\n但风一吹，露出来的手指又提醒所有人：\\n\\n他们还在这里。 | Patch 007-2 | 雪下尸列 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.bodies_under_snow.option_a | Event / Death | 选项 | 承诺处理遗体 | Patch 007-2 | 雪下尸列 | 已封存原文 | 玩家可见 |  |
| event.bodies_under_snow.option_b | Event / Death | 选项 | 举行临时悼念 | Patch 007-2 | 雪下尸列 | 已封存原文 | 玩家可见 | 悼念不能替代遗体处理。 |
| event.bodies_under_snow.option_c | Event / Death | 选项 | 继续搁置 | Patch 007-2 | 雪下尸列 | 已封存原文 | 玩家可见 |  |
| event.children_request.title | Event / Children | 事件标题 | 孩子们的请求 | Patch 007-2 | 儿童事件一 | 已封存原文 | 玩家可见 |  |
| event.children_request.body | Event / Children | 事件正文 | 几个孩子站在炉边，没有靠得太近。\\n\\n他们问执政官：\\n\\n我们今天要去哪儿？\\n\\n没人回答。\\n因为城市还没决定，孩子在这里算未来，还是算劳动力。 | Patch 007-2；总控 | 孩子们的请求 / 描述方向 | 用户确认覆盖项 | 玩家可见 | 原文“守炉人”按玩家身份总控改为“执政官”。 |
| event.children_request.option_a | Event / Children | 选项 | 承诺安置儿童 | Patch 007-2 | 孩子们的请求 | 已封存原文 | 玩家可见 |  |
| event.children_request.option_b | Event / Children | 选项 | 暂时维持现状 | Patch 007-2 | 孩子们的请求 | 已封存原文 | 玩家可见 |  |
| event.children_request.option_c | Event / Children | 选项 | 安排炉边杂务 | Patch 007-2 | 孩子们的请求 | 已封存原文 | 玩家可见 | 不提供正式劳动力收益。 |
| event.red_frozen_hands.title | Event / Children | 事件标题 | 冻红的手 | Patch 007-2 | 儿童事件二 | 已封存原文 | 玩家可见 |  |
| event.red_frozen_hands.body | Event / Children | 事件正文 | 一个孩子把手藏在袖子里。\\n\\n医生让他伸出来。\\n他不肯。\\n\\n后来人们才看见，那双手已经冻得发红，指节肿得像小块木炭。 | Patch 007-2 | 冻红的手 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.red_frozen_hands.option_a | Event / Children | 选项 | 暂停儿童高风险劳动 | Patch 007-2 | 冻红的手 | 已封存原文 | 玩家可见 |  |
| event.red_frozen_hands.option_b | Event / Children | 选项 | 提供额外防寒照料 | Patch 007-2 | 冻红的手 | 已封存原文 | 玩家可见 | 消耗熟食。 |
| event.red_frozen_hands.option_c | Event / Children | 选项 | 继续维持安排 | Patch 007-2 | 冻红的手 | 已封存原文 | 玩家可见 |  |
| event.long_shift_collapse.title | Event / Labor | 事件标题 | 长班后的倒下 | Patch 007-2 | 工时事件一 | 已封存原文 | 玩家可见 |  |
| event.long_shift_collapse.body | Event / Labor | 事件正文 | TODO_TEXT | Patch 007-2 | 长班后的倒下 | TODO_TEXT | 玩家可见 | 原文件没有封存完整事件正文。 |
| event.long_shift_collapse.option_a | Event / Labor | 选项 | 暂停长班一天 | Patch 007-2 | 长班后的倒下 | 已封存原文 | 玩家可见 |  |
| event.long_shift_collapse.option_b | Event / Labor | 选项 | 提供熟食补偿 | Patch 007-2 | 长班后的倒下 | 已封存原文 | 玩家可见 |  |
| event.long_shift_collapse.option_c | Event / Labor | 选项 | 继续长班 | Patch 007-2 | 长班后的倒下 | 已封存原文 | 玩家可见 |  |
| event.overtime_empty_post.title | Event / Labor | 事件标题 | 加班后的空位 | Patch 007-2 | 工时事件二 | 已封存原文 | 玩家可见 |  |
| event.overtime_empty_post.body | Event / Labor | 事件正文 | TODO_TEXT | Patch 007-2 | 加班后的空位 | TODO_TEXT | 玩家可见 | 原文件没有封存完整事件正文。 |
| event.overtime_empty_post.option_a | Event / Labor | 选项 | 承诺补足人手或降低过劳压力 | Patch 007-2 | 加班后的空位 | 已封存原文 | 玩家可见 |  |
| event.overtime_empty_post.option_b | Event / Labor | 选项 | 提供熟食补偿 | Patch 007-2 | 加班后的空位 | 已封存原文 | 玩家可见 |  |
| event.overtime_empty_post.option_c | Event / Labor | 选项 | 继续维持安排 | Patch 007-2 | 加班后的空位 | 已封存原文 | 玩家可见 |  |
  
   
⸻  
   
## 05_Event / 核心系统危机事件正文  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------------- | --------------- | ----- | ---------------------------------------------------------------------------- | -------------- | ----------- | ------- | ---- | ------------------------------- |
| event.coal_bottom.title | Event / Coal | 事件标题 | 煤仓见底 | Patch 007-2 | 核心事件一 | 已封存原文 | 玩家可见 |  |
| event.coal_bottom.body | Event / Coal | 事件正文 | 煤仓底部露出来了。\\n\\n铲子碰到木板时，声音比风还空。 | Patch 007-2 | 煤仓见底 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.coal_bottom.option_a | Event / Coal | 选项 | 承诺补足煤炭储备 | Patch 007-2 | 煤仓见底 | 已封存原文 | 玩家可见 |  |
| event.coal_bottom.option_b | Event / Coal | 选项 | 调整炉心消耗 | Patch 007-2 | 煤仓见底 | 用户确认覆盖项 | 玩家可见 | 仅提示命令，不自动修改炉心 / 过载 / woodfuel。 |
| event.coal_bottom.option_c | Event / Coal | 选项 | 维持现状 | Patch 007-2 | 煤仓见底 | 已封存原文 | 玩家可见 |  |
| event.furnace_redline.title | Event / Furnace | 事件标题 | 炉心红线 | Patch 007-2 | 核心事件二 | 已封存原文 | 玩家可见 |  |
| event.furnace_redline.warning | Event / Furnace | 强制警告 | 炉心压力已达到极限。\\n这是最后一次手动关闭过载的机会。\\n若继续维持过载，下一次日结可能导致炉心崩毁。 | Patch 007-2 | 炉心红线 / 显示提示 | 已封存原文 | 玩家可见 | 压力 100 强制警告不受普通冷却屏蔽。 |
| event.furnace_redline.option_a | Event / Furnace | 选项 | 立即关闭过载 | Patch 007-2 | 炉心红线 | 用户确认覆盖项 | 玩家可见 | 选项只提示执行 overload off，事件本身不自动关闭。 |
| event.furnace_redline.option_b | Event / Furnace | 选项 | 承诺完成炉心减压方案 | Patch 007-2 | 炉心红线 | 已封存原文 | 玩家可见 | 无有效目标时不可用。 |
| event.furnace_redline.option_c | Event / Furnace | 选项 | 维持过载 / 暂不处理 | Patch 007-2 | 炉心红线 | 已封存原文 | 玩家可见 |  |
| event.cold_house_night.title | Event / Housing | 事件标题 | 寒屋之夜 | Patch 007-2 | 核心事件三 | 已封存原文 | 玩家可见 |  |
| event.cold_house_night.body | Event / Housing | 事件正文 | 夜里，有人把炉灰抹在墙缝上。\\n\\n没有用。\\n\\n风还是从缝里钻进来，摸过孩子的脚踝，摸过老人的膝盖，最后停在每个人的肺里。 | Patch 007-2 | 寒屋之夜 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.cold_house_night.option_a | Event / Housing | 选项 | 承诺补足住房 / 保温 | Patch 007-2 | 寒屋之夜 | 已封存原文 | 玩家可见 |  |
| event.cold_house_night.option_b | Event / Housing | 选项 | 提高炉心档位 | Patch 007-2 | 寒屋之夜 | 用户确认覆盖项 | 玩家可见 | 仅提示玩家执行命令，不自动提高档位。 |
| event.cold_house_night.option_c | Event / Housing | 选项 | 维持现状 | Patch 007-2 | 寒屋之夜 | 已封存原文 | 玩家可见 |  |
| event.trust_crack.title | Event / Trust | 事件标题 | 信任裂缝 | Patch 007-2 | 核心事件四 | 已封存原文 | 玩家可见 |  |
| event.trust_crack.body | Event / Trust | 事件正文 | 人们还在工作。\\n\\n他们仍然走向矿井、食堂、医疗站和炉边。\\n但他们不再看执政官的眼睛。\\n\\n城市没有立刻崩塌。\\n只是有一根东西断了。 | Patch 007-2；总控 | 信任裂缝 / 描述方向 | 用户确认覆盖项 | 玩家可见 | 原文“守炉人”按玩家身份总控改为“执政官”。 |
| event.trust_crack.option_a | Event / Trust | 选项 | 承诺恢复信任 | Patch 007-2 | 信任裂缝 | 已封存原文 | 玩家可见 |  |
| event.trust_crack.option_b | Event / Trust | 选项 | 发布安抚公告 / 公开说明 | Patch 007-2 | 信任裂缝 | 已封存原文 | 玩家可见 | 根据当前可用手段显示。 |
| event.trust_crack.option_c | Event / Trust | 选项 | 维持现状 | Patch 007-2 | 信任裂缝 | 已封存原文 | 玩家可见 |  |
| event.trust_crack.final_oath_warning | Event / Trust | 非失败警告 | 信任已崩溃。\\n终火誓约正在承接其后果。\\n\\n提示：信任虽然不再导致直接失败，但仍会影响旧城派增长、居民事件与终局评价。 | Patch 007-2 | 终火誓约生效时 | 已封存原文 | 玩家可见 |  |
| event.city_unrest.title | Event / Panic | 事件标题 | 炉城骚动 | Patch 007-2 | 核心事件五 | 已封存原文 | 玩家可见 |  |
| event.city_unrest.body | Event / Panic | 事件正文 | 有人在夜里喊了一声。\\n\\n很快，更多人醒了。\\n他们不知道自己要去哪里，也不知道自己要找谁。\\n\\n恐惧在炉城里跑得比人更快。 | Patch 007-2 | 炉城骚动 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.city_unrest.option_a | Event / Panic | 选项 | 承诺降低恐慌 | Patch 007-2 | 炉城骚动 | 已封存原文 | 玩家可见 |  |
| event.city_unrest.option_b | Event / Panic | 选项 | 组织安抚 / 巡查 | Patch 007-2 | 炉城骚动 | 已封存原文 | 玩家可见 | 根据当前可用手段显示。 |
| event.city_unrest.option_c | Event / Panic | 选项 | 维持现状 | Patch 007-2 | 炉城骚动 | 已封存原文 | 玩家可见 |  |
| event.city_unrest.supreme_order_warning | Event / Panic | 非失败警告 | 恐慌已失控。\\n最高戒令正在压制其后果。\\n\\n提示：恐慌虽然不再导致直接失败，但仍会影响旧城派增长、居民事件与终局评价。 | Patch 007-2 | 最高戒令生效时 | 已封存原文 | 玩家可见 |  |
  
   
⸻  
   
## 06_OldCity / 旧城派事件链  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------------- | ---------------- | ----- | ---------------------------------------------------- | ------------------- | ------------ | ---------------- | ---- | ---------------------- |
| old_city.system.name | OldCity | 系统名 | 旧城派 | Patch 007-1 | 旧城派定位 | 已封存原文 | 通用 |  |
| old_city.event.southern_letter.title | OldCity / Event | 事件标题 | 南方来信 | Patch 007-1 / 第六批补表 | 阶段 1 | 已封存原文 | 玩家可见 | 第 24 天固定触发。 |
| old_city.event.southern_letter.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 阶段 1：南方来信 | TODO_TEXT | 玩家可见 | 只封存作用和选项方向，完整叙事正文未封存。 |
| old_city.event.southern_letter.option_a | OldCity / Event | 选项 | 公布来信 | Patch 007-1 / 第六批补表 | 南方来信 | 已封存原文 | 玩家可见 |  |
| old_city.event.southern_letter.option_b | OldCity / Event | 选项 | 压下来信 | Patch 007-1 / 第六批补表 | 南方来信 | 已封存原文 | 玩家可见 |  |
| old_city.event.hidden_rumors.title | OldCity / Event | 事件标题 | 暗中传言 | Patch 007-1 | 阶段 2 | 已封存原文 | 玩家可见 |  |
| old_city.event.hidden_rumors.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 阶段 2：暗中传言 | TODO_TEXT | 玩家可见 | 完整正文未封存。 |
| old_city.event.hidden_rumors.option_a | OldCity / Event | 选项 | 公开解释 | Patch 007-1 / 第六批补表 | 暗中传言 | 已封存原文 | 玩家可见 |  |
| old_city.event.hidden_rumors.option_b | OldCity / Event | 选项 | 暂不处理 | Patch 007-1 / 第六批补表 | 暗中传言 | 已封存原文 | 玩家可见 |  |
| old_city.event.public_gathering.title | OldCity / Event | 事件标题 | 公开集结 | Patch 007-1 | 阶段 3 | 已封存原文 | 玩家可见 |  |
| old_city.event.public_gathering.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 阶段 3：公开集结 | TODO_TEXT | 玩家可见 | 完整正文未封存。 |
| old_city.count.label | OldCity / UI | UI 标签 | 旧城派人数：X | Patch 007-1 | 公开集结 / 显示方向 | 已封存原文 | 玩家可见 |  |
| old_city.trend.label | OldCity / UI | UI 标签 | 趋势：增长 / 持平 / 下降 | Patch 007-1 | 公开集结 / 显示方向 | 已封存原文 | 玩家可见 |  |
| old_city.event.public_gathering.option_a | OldCity / Event | 选项 | 公开说明 | Patch 007-1 / 第六批补表 | 公开集结 | 已封存原文 | 玩家可见 | 不锁定誓言路线。 |
| old_city.event.public_gathering.option_b | OldCity / Event | 选项 | 加强巡查 | Patch 007-1 / 第六批补表 | 公开集结 | 已封存原文 | 玩家可见 | 不锁定铁腕路线。 |
| old_city.event.public_gathering.option_c | OldCity / Event | 选项 | 暂不处理 | Patch 007-1 / 第六批补表 | 公开集结 | 已封存原文 | 玩家可见 |  |
| old_city.event.exodus_countdown.title | OldCity / Event | 事件标题 | 离城倒计时 | Patch 007-1 | 阶段 4 | 已封存原文 | 玩家可见 |  |
| old_city.event.exodus_countdown.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 阶段 4：离城倒计时 | TODO_TEXT | 玩家可见 | 完整正文未封存。 |
| old_city.event.exodus_countdown.option_a | OldCity / Event | 选项 | 承诺压低旧城派人数 | 第六批补表 | 阶段 4 最新选项 | 代码窗暂定实现值 / 测试窗必测 | 玩家可见 | 创建旧城派承诺。 |
| old_city.event.exodus_countdown.option_b | OldCity / Event | 选项 | 暂不阻拦 | 第六批补表 | 阶段 4 最新选项 | 代码窗暂定实现值 / 测试窗必测 | 玩家可见 | 覆盖旧版“不再阻拦 / 争取时间”排序。 |
| old_city.event.exodus_countdown.option_c | OldCity / Event | 选项 | 争取最后时间 | 第六批补表 | 阶段 4 最新选项 | 代码窗暂定实现值 / 测试窗必测 | 玩家可见 | 需要信任达到条件或已选择誓言 / 铁腕路线。 |
| old_city.result.scattered.name | OldCity / Result | 结果名 | 旧城派散去 | Patch 007-1 / 第六批补表 | 最终结算 | 已封存原文 | 玩家可见 |  |
| old_city.result.partial_exodus.name | OldCity / Result | 结果名 | 部分出走 | Patch 007-1 / 第六批补表 | 最终结算 | 已封存原文 | 玩家可见 | 出走不是死亡。 |
| old_city.result.large_exodus.name | OldCity / Result | 结果名 | 大规模出走 | Patch 007-1 / 第六批补表 | 最终结算 | 已封存原文 | 玩家可见 | 不是系统硬失败。 |
| old_city.result.scattered.tag | OldCity / Ending | 终局标签 | 炉城裂缝被压住 | Patch 007-1 / 第六批补表 | 旧城派散去 | 已封存原文 | 玩家可见 |  |
| old_city.rule.route_action_requirement | OldCity / Route | 内部规则 | 路线已选择、对应炉律已签署、对应路线承接物已启用并运行、行动不在冷却中、旧城派危机已激活且人数大于 0。 | Patch 007-1；全局总控 | 旧城派与 006C 接口 | 用户确认覆盖项 | 系统内部 | 不使用“核心建筑已建成”。 |
| old_city.rule.no_total_exodus | OldCity | 内部规则 | V1 不做全员出走；普通难度保留最低工程师保护线。 | Patch 007-1 / 第六批补表 | 最终结算 | 已封存原文 | 系统内部 |  |
| old_city.rule.exodus_not_death | OldCity | 内部规则 | 旧城派出走不是死亡，不进入遗体系统，也不是系统硬失败。 | 第六批补表 | 最终结算 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
  
   
⸻  
   
## 07_FixedArrival / 固定增员事件  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------- | ---------------------- | ---- | -------------------------------------- | ------------------- | ---------- | --------- | ---- | -------------------- |
| arrival.option.accept_all | FixedArrival | 通用选项 | 全部接纳 | Patch 007-1 / 第五批补表 | 接纳选项总规则 | 已封存原文 | 玩家可见 |  |
| arrival.option.accept_partial | FixedArrival | 通用选项 | 部分接纳 | Patch 007-1 / 第五批补表 | 接纳选项总规则 | 已封存原文 | 玩家可见 | 不允许玩家手动输入人数。 |
| arrival.option.reject | FixedArrival | 通用选项 | 拒绝接纳 | Patch 007-1 / 第五批补表 | 接纳选项总规则 | 已封存原文 | 玩家可见 |  |
| arrival.day6.title | FixedArrival / Event | 事件标题 | 早期求生者 | Patch 007-1 / 第五批补表 | 第 6 天固定增员 | 已封存原文 | 玩家可见 | 第 6 天固定触发。 |
| arrival.day6.body | FixedArrival / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 第一批：早期求生者 | TODO_TEXT | 玩家可见 | 仅封存定位与选项后果，叙事正文未封存。 |
| arrival.day19.title | FixedArrival / Event | 事件标题 | 中期工程残队 | Patch 007-1 / 第五批补表 | 第 19 天固定增员 | 已封存原文 | 玩家可见 | 第 19 天固定触发。 |
| arrival.day19.body | FixedArrival / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 第二批：中期工程残队 | TODO_TEXT | 玩家可见 | 叙事正文未封存。 |
| arrival.day37.title | FixedArrival / Event | 事件标题 | 后期难民潮 | Patch 007-1 / 第五批补表 | 第 37 天固定增员 | 已封存原文 | 玩家可见 | 第 37 天固定触发。 |
| arrival.day37.body | FixedArrival / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 第三批：后期难民潮 | TODO_TEXT | 玩家可见 | 叙事正文未封存。 |
| arrival.work_assignment.notice | FixedArrival / Workers | 系统提示 | 新增人口当天能够工作，但不会自动分配岗位。请手动调整工作分配。 | Patch 007-1 | 固定增员与工作分配 | 用户确认覆盖项 | 玩家可见 | 将封存说明整理为可显示提示，不改变机制。 |
| arrival.immediate_pressure.notice | FixedArrival / Warning | 系统提示 | 新增人口已经进城，并立即计入住房、食物、医疗和疾病压力。 | Patch 007-1 | 新人口生效时机 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.rule.major_event | FixedArrival | 内部规则 | 固定增员是固定日期重大事件，每局各触发一次，必须处理后才能 end_day。 | Patch 007-1 / 第五批补表 | 固定增员总原则 | 已封存原文 | 系统内部 |  |
| arrival.rule.no_manual_count | FixedArrival | 内部规则 | V1 不允许玩家手动输入接纳人数，部分接纳人数由系统预设。 | Patch 007-1 / 第五批补表 | 接纳选项总规则 | 已封存原文 | 系统内部 |  |
| arrival.rule.immediate_effect | FixedArrival | 内部规则 | 新增人口立即加入人口池，并参与当日住房、食物、医疗和疾病压力。 | Patch 007-1 / 第五批补表 | 新人口生效时机 | 已封存原文 | 系统内部 |  |
| arrival.rule.no_auto_workers | FixedArrival | 内部规则 | 新增健康人口不自动分配岗位。 | Patch 007-1 / 第五批补表 | 固定增员与工作分配 | 已封存原文 | 系统内部 |  |
  
   
⸻  
   
## 08_FixedArrival / 固定增员内部实现值  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------- | ------------ | ------ | --------------------------------------------------------------------------------- | ----- | ----------- | ---------------- | ---- | ------------------------ |
| arrival.day6.accept_all.internal | FixedArrival | 内部数值说明 | 全部接纳：共 12 人；6 名工人、3 名儿童、2 名患病人口、1 名重症人口；信任 +3，恐慌 -1。 | 第五批补表 | 第 6 天：全部接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 不作为玩家明牌数值，除非 UI 后续确认可预览。 |
| arrival.day6.accept_partial.internal | FixedArrival | 内部数值说明 | 部分接纳：共 6 人；3 名工人、1 名儿童、1 名患病人口、1 名重症人口；信任 +1，恐慌 +1。 | 第五批补表 | 第 6 天：部分接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| arrival.day6.reject.internal | FixedArrival | 内部数值说明 | 拒绝接纳：不增加人口；信任 -4，恐慌 +4。 | 第五批补表 | 第 6 天：拒绝接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| arrival.day19.accept_all.internal | FixedArrival | 内部数值说明 | 全部接纳：共 20 人；10 名工人、4 名工程师、2 名儿童、2 名患病人口、1 名重症人口、1 名伤残人口；信任 +3，恐慌不变。 | 第五批补表 | 第 19 天：全部接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| arrival.day19.accept_partial.internal | FixedArrival | 内部数值说明 | 部分接纳：共 10 人；5 名工人、2 名工程师、1 名儿童、1 名患病人口、1 名伤残人口；信任 +1，恐慌 +1。 | 第五批补表 | 第 19 天：部分接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| arrival.day19.reject.internal | FixedArrival | 内部数值说明 | 拒绝接纳：不增加人口；信任 -5，恐慌 +5。 | 第五批补表 | 第 19 天：拒绝接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 第 24 天前不直接增加旧城派人数。 |
| arrival.day37.accept_all.internal | FixedArrival | 内部数值说明 | 全部接纳：共 36 人；14 名工人、2 名工程师、8 名儿童、7 名患病人口、3 名重症人口、2 名伤残人口；信任 +4，恐慌 +2；旧城派已激活时人数 -5。 | 第五批补表 | 第 37 天：全部接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| arrival.day37.accept_partial.internal | FixedArrival | 内部数值说明 | 部分接纳：共 16 人；7 名工人、1 名工程师、3 名儿童、3 名患病人口、1 名重症人口、1 名伤残人口；信任 -1，恐慌 +3；旧城派已激活时人数 +4。 | 第五批补表 | 第 37 天：部分接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 后期部分接纳不是中性选项。 |
| arrival.day37.reject.internal | FixedArrival | 内部数值说明 | 拒绝接纳：不增加人口；信任 -8，恐慌 +8；旧城派已激活时人数 +10。 | 第五批补表 | 第 37 天：拒绝接纳 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 不直接触发失败或最终出走。 |
  
   
⸻  
   
## 09_ArrivalPreview / 固定增员风险预览  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------------- | ---------------------- | ----- | ----------------- | ----- | --------- | ------- | ---- | ----------------- |
| arrival.preview.title | FixedArrival / UI | UI 标题 | 接纳后风险预览 | 第五批补表 | 固定增员风险预览 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.population.label | FixedArrival / UI | UI 标签 | 接纳后人口 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.housing.label | FixedArrival / UI | UI 标签 | 住房容量 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.homeless.label | FixedArrival / UI | UI 标签 | 接纳后无住所人口 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.food_days.label | FixedArrival / UI | UI 标签 | 接纳后食物可维持天数 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.medical_capacity.label | FixedArrival / UI | UI 标签 | 医疗容量 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.medical_gap.label | FixedArrival / UI | UI 标签 | 接纳后医疗缺口 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.sick.label | FixedArrival / UI | UI 标签 | 接纳后患病人口 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.severe.label | FixedArrival / UI | UI 标签 | 接纳后重症人口 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.disabled.label | FixedArrival / UI | UI 标签 | 接纳后伤残人口 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.children.label | FixedArrival / UI | UI 标签 | 接纳后儿童人数 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.trust.label | FixedArrival / UI | UI 标签 | 接纳后信任 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 | 是否显示具体数值由 UI 决定。 |
| arrival.preview.panic.label | FixedArrival / UI | UI 标签 | 接纳后恐慌 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 | 是否显示具体数值由 UI 决定。 |
| arrival.preview.old_city.label | FixedArrival / UI | UI 标签 | 接纳后旧城派变化 | 第五批补表 | 风险预览字段 | 用户确认覆盖项 | 玩家可见 | 仅在旧城派已激活且发生变化时显示。 |
| arrival.preview.housing_risk | FixedArrival / Warning | 风险提示 | 接纳后将出现住房风险。 | 第五批补表 | 风险提示 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.food_risk | FixedArrival / Warning | 风险提示 | 接纳后食物储备可能不足。 | 第五批补表 | 风险提示 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.medical_risk | FixedArrival / Warning | 风险提示 | 接纳后将出现医疗容量缺口。 | 第五批补表 | 风险提示 | 用户确认覆盖项 | 玩家可见 |  |
| arrival.preview.old_city_risk | FixedArrival / Warning | 风险提示 | 该选择将影响旧城派人数或增长趋势。 | 第五批补表 | 风险提示 | 用户确认覆盖项 | 玩家可见 |  |
  
   
⸻  
   
## 10_Event / 事件冷却与次数内部口径  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------- | ----- | ---- | ----------------------------------- | ------------------- | --------- | ---------------- | ---- | ------------------------- |
| event.empty_pot.cooldown | Event | 内部冷却 | 空锅请愿可重复，同类冷却 4 天。 | Patch 007-2 / 第五批补表 | 事件次数与冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| event.raw_food_dispute.limit | Event | 内部次数 | 生食争议每局最多触发 1 次。 | Patch 007-2 / 第五批补表 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.medical_beds_emergency.cooldown | Event | 内部冷却 | 病床告急可重复，同类冷却 4 天。 | Patch 007-2 / 第五批补表 | 事件次数与冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| event.severe_case_backlog.limit | Event | 内部次数 | 重症积压每局最多触发 1 次，或作为医疗类升级事件。 | Patch 007-2 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.first_body.limit | Event | 内部次数 | 第一具遗体每局只触发 1 次。 | Patch 007-2 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.bodies_under_snow.cooldown | Event | 内部冷却 | 雪下尸列可重复，同类冷却 4 天。 | Patch 007-2 / 第五批补表 | 事件次数与冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| event.children_request.limit | Event | 内部次数 | 孩子们的请求每局最多触发 1 次。 | Patch 007-2 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.red_frozen_hands.limit | Event | 内部次数 | 冻红的手每局最多触发 1 次。 | Patch 007-2 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.long_shift_collapse.limit | Event | 内部次数 | 长班后的倒下每局最多触发 1 次。 | Patch 007-2 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.overtime_empty_post.limit | Event | 内部次数 | 加班后的空位每局最多触发 2 次。 | Patch 007-2 | 事件次数与冷却 | 已封存原文 | 系统内部 |  |
| event.coal_bottom.cooldown | Event | 内部冷却 | 煤仓见底可重复，同类冷却 5 天。 | Patch 007-2 / 第五批补表 | 核心事件冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| event.furnace_redline.cooldown | Event | 内部冷却 | 炉心红线可重复，同类冷却 4 天；压力 100 强制警告不受冷却屏蔽。 | Patch 007-2 / 第五批补表 | 核心事件冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| event.cold_house_night.cooldown | Event | 内部冷却 | 寒屋之夜同类冷却 4 天；第七霜落期间不再新开。 | 第五批补表 | 核心事件冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 覆盖 Patch 007-2 旧“冷却 5 天”。 |
| event.trust_crack.cooldown | Event | 内部冷却 | 信任裂缝同类冷却 5 天。 | 第五批补表 | 核心事件冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 危机状态仍持续结算。 |
| event.city_unrest.cooldown | Event | 内部冷却 | 炉城骚动同类冷却 5 天。 | 第五批补表 | 核心事件冷却 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 危机状态仍持续结算。 |
  
   
⸻  
   
## 11_FrostWarning / 第七霜落预警事件  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------------- | -------------------- | ----- | -------------------------------------------------------------------------------------------------------- | ----------- | -------------- | --------- | ---- | -------------------- |
| frost.warning.preparation.title | FrostWarning / UI | UI 标题 | 第七霜落准备 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 | 从第 34 天开始显示。 |
| frost.warning.days_remaining.label | FrostWarning / UI | UI 标签 | 剩余天数：X | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| frost.warning.coal.label | FrostWarning / UI | UI 标签 | 煤炭储备：不足 / 勉强 / 充足 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 | 阈值按第七批补表。 |
| frost.warning.food.label | FrostWarning / UI | UI 标签 | 熟食储备：不足 / 勉强 / 充足 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| frost.warning.housing.label | FrostWarning / UI | UI 标签 | 住房保护：不足 / 勉强 / 稳定 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| frost.warning.medical.label | FrostWarning / UI | UI 标签 | 医疗容量：不足 / 勉强 / 稳定 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| frost.warning.furnace_pressure.label | FrostWarning / UI | UI 标签 | 炉心压力：安全 / 偏高 / 危险 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| frost.warning.old_city.label | FrostWarning / UI | UI 标签 | 旧城派：未激活 / 稳定 / 高风险 / 倒计时中 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| frost.warning.route.label | FrostWarning / UI | UI 标签 | 誓言 / 铁腕：未开放 / 未选择 / 推进中 / 终章完成 | Patch 007-3 | 终局准备清单 | 已封存原文 | 玩家可见 |  |
| event.black_frost_echo.title | FrostWarning / Event | 事件标题 | 黑霜回声 | Patch 007-3 | 第 34 天事件 | 已封存原文 | 玩家可见 |  |
| event.black_frost_echo.body | FrostWarning / Event | 事件正文 | 夜里，炉城外传来一种很低的声音。\\n\\n不是风。\\n也不是雪。\\n\\n像有什么东西正在很远的地方压过冻土，把世界一点点磨平。\\n\\n工程师说，黑霜的回声已经到了。\\n真正的第七霜落，还在路上。 | Patch 007-3 | 黑霜回声 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.black_frost_echo.option_a | FrostWarning / Event | 选项 | 公开预警 | Patch 007-3 | 黑霜回声 | 已封存原文 | 玩家可见 |  |
| event.black_frost_echo.option_b | FrostWarning / Event | 选项 | 只通知管理与工程人员 | Patch 007-3 | 黑霜回声 | 已封存原文 | 玩家可见 |  |
| event.black_frost_echo.option_c | FrostWarning / Event | 选项 | 暂缓公布 | Patch 007-3 | 黑霜回声 | 已封存原文 | 玩家可见 |  |
| event.final_preparation_window.title | FrostWarning / Event | 事件标题 | 最后的整备窗口 | Patch 007-3 | 第 42 天事件 | 已封存原文 | 玩家可见 |  |
| event.final_preparation_window.body | FrostWarning / Event | 事件正文 | 炉城的晨钟敲了很久。\\n\\n没有人迟到。\\n没有人说话。\\n\\n他们都看见了天边那道灰白色的墙。\\n它还没有压下来，但已经挡住了太阳。 | Patch 007-3 | 最后的整备窗口 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.final_preparation_window.option_a | FrostWarning / Event | 选项 | 公开最后整备清单 | Patch 007-3 | 最后的整备窗口 | 已封存原文 | 玩家可见 |  |
| event.final_preparation_window.option_b | FrostWarning / Event | 选项 | 只向管理层通报 | Patch 007-3 | 最后的整备窗口 | 已封存原文 | 玩家可见 |  |
| event.final_preparation_window.option_c | FrostWarning / Event | 选项 | 压下恐慌，继续日常运转 | Patch 007-3 | 最后的整备窗口 | 已封存原文 | 玩家可见 |  |
| event.city_night_terror.title | FrostWarning / Event | 事件标题 | 炉城夜惊 | Patch 007-3 | 第 46 天事件 | 已封存原文 | 玩家可见 |  |
| event.city_night_terror.body | FrostWarning / Event | 事件正文 | 那一夜，没有人真正睡着。\\n\\n炉城外的雪声像兽群在低伏。\\n有人把孩子抱得很紧。\\n有人一遍遍数煤仓。\\n有人问工程师：\\n\\n炉心还能撑几天？\\n\\n工程师没有回答。 | Patch 007-3 | 炉城夜惊 / 描述方向 | 已封存原文 | 玩家可见 |  |
| event.city_night_terror.option_a | FrostWarning / Event | 选项 | 发布最终动员 | Patch 007-3 | 炉城夜惊 | 已封存原文 | 玩家可见 |  |
| event.city_night_terror.option_b | FrostWarning / Event | 选项 | 维持秩序，避免恐慌 | Patch 007-3 | 炉城夜惊 | 已封存原文 | 玩家可见 |  |
| event.city_night_terror.option_c | FrostWarning / Event | 选项 | 不再粉饰情况 | Patch 007-3 | 炉城夜惊 | 已封存原文 | 玩家可见 |  |
| event.frost_eve.title | FrostWarning | 提示标题 | 霜落前夜 | Patch 007-3 | 第 48 天提示 | 已封存原文 | 玩家可见 | 非阻塞氛围提示。 |
| event.frost_eve.body | FrostWarning | 提示正文 | 风停了。\\n\\n这比风还可怕。\\n\\n炉城外的雪原像一张没有写完的白纸。\\n所有人都知道，明天会有什么东西落下来。 | Patch 007-3 | 霜落前夜 / 描述方向 | 已封存原文 | 玩家可见 | 不给选项、不改变资源或情绪。 |
| event.seventh_frost_start.title | FrostWarning / Event | 事件标题 | 第七霜落 | Patch 007-3 | 第 49 天事件 | 已封存原文 | 玩家可见 | 第 49～55 天为固定终局阶段。 |
| event.seventh_frost_start.body | FrostWarning / Event | 事件正文 | TODO_TEXT | Patch 007-3 | 第七霜落开始 | TODO_TEXT | 玩家可见 | 原文件只封存事件作用，没有完整叙事正文。 |
  
   
⸻  
   
## 12_Achievement / 隐藏成就与彩蛋  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------- | ----------- | ---- | ------------------------------------- | ----------- | ----------- | ----- | ---- | --------------- |
| achievement.cold_death.title | Achievement | 成就名 | 冷吗？死了就不冷了 | Patch 007-3 | 隐藏成就 | 已封存原文 | 玩家可见 |  |
| achievement.cold_death.desc | Achievement | 成就描述 | 你成功解决了居民的寒冷问题——以一种不建议写进政绩报告的方式。 | Patch 007-3 | 隐藏成就 | 已封存原文 | 玩家可见 |  |
| achievement.cold_death.note | Achievement | 彩蛋附注 | 备注：本成就由畜生流执政官兼制作组友情冠名。 | Patch 007-3 | 隐藏成就 / 可选附注 | 待确认 | 待判定 | 可保留或隐藏；不影响成就触发。 |
| achievement.rule.no_balance_effect | Achievement | 内部规则 | 隐藏成就不影响游戏平衡，不占事件名额，也不阻止失败。 | Patch 007-3 | 隐藏成就规则 | 已封存原文 | 系统内部 |  |
| achievement.rule.cold_death_scope | Achievement | 内部规则 | 仅在玩家主动关闭炉心过夜并造成本局首例寒冷死亡时触发，不是所有冻死都触发。 | Patch 007-3 | 隐藏成就触发限制 | 已封存原文 | 系统内部 |  |
  
   
⸻  
   
## 13_Internal / 承诺内部期限与奖惩分档  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------- | ------- | ---- | ------------------------------------------------- | ----- | --------- | ---------------- | ---- | ------------------------- |
| promise.duration.light.internal | Promise | 内部期限 | 轻度承诺期限为 3 天。 | 第五批补表 | 承诺期限分档 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.duration.medium.internal | Promise | 内部期限 | 中度承诺期限为 4 天。 | 第五批补表 | 承诺期限分档 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.duration.heavy.internal | Promise | 内部期限 | 重度承诺期限为 5 天。 | 第五批补表 | 承诺期限分档 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.reward.ordinary.internal | Promise | 内部奖惩 | 普通承诺成功：信任 +2、恐慌 -1；失败：信任 -6、恐慌 +6。 | 第五批补表 | 承诺奖惩分档 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.reward.serious.internal | Promise | 内部奖惩 | 严重承诺成功：信任 +3、恐慌 -2；失败：信任 -8、恐慌 +8。 | 第五批补表 | 承诺奖惩分档 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.reward.critical.internal | Promise | 内部奖惩 | 临界承诺成功：信任 +4、恐慌 -3；失败：信任 -10、恐慌 +10。 | 第五批补表 | 承诺奖惩分档 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.food.target.internal | Promise | 内部目标 | 食物承诺默认 3 天；可食用食物至少覆盖存活人口 2 天，熟食至少覆盖存活人口 1 天。 | 第五批补表 | 食物承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 允许食堂可运行且可加工生食补足熟食缺口的替代判定。 |
| promise.medical.target.internal | Promise | 内部目标 | 医疗承诺默认 4 天；至少有一座可运行医疗站或医院，且有效医疗容量不低于患病与重症总数。 | 第五批补表 | 医疗承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.housing.target.internal | Promise | 内部目标 | 住房承诺默认 4 天；无住所人口必须降为 0。 | 第五批补表 | 住房承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 儿童保护所、学堂、临时避寒点不提供正式住房容量。 |
| promise.body.target.internal | Promise | 内部目标 | 遗体处理承诺默认 3 天；未处理遗体必须降为 0。 | 第五批补表 | 遗体处理承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.children.target.internal | Promise | 内部目标 | 儿童安置承诺默认 4 天；未受保护儿童必须降为 0。 | 第五批补表 | 儿童承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 儿童安置不等于住房问题已解决。 |
| promise.labor.target.internal | Promise | 内部目标 | 工时 / 过劳承诺默认 3 天；近 2 天未使用加班日，长班关闭或暂停，且没有新增过劳伤病或死亡。 | 第五批补表 | 工时承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 |  |
| promise.coal.target.internal | Promise | 内部目标 | 煤炭承诺默认 3 天；煤炭库存至少达到当前炉心基础煤耗的 2 倍。 | 第五批补表 | 煤炭承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | woodfuel 不计入煤炭库存。 |
| promise.furnace.target.internal | Promise | 内部目标 | 炉心压力承诺默认 4 天；炉心压力不高于 70，且过载关闭。 | 第五批补表 | 炉心压力承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 压力 100 附近使用临界奖惩。 |
| promise.trust.target.internal | Promise | 内部目标 | 信任承诺默认 4 天；信任达到 40，或较承诺创建时提高至少 8 点。 | 第五批补表 | 信任承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 两者满足其一即可。 |
| promise.panic.target.internal | Promise | 内部目标 | 恐慌承诺默认 4 天；恐慌降至 60，或较承诺创建时降低至少 8 点。 | 第五批补表 | 恐慌承诺目标 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 两者满足其一即可。 |
| promise.old_city.target.internal | Promise | 内部目标 | 旧城派承诺默认 5 天；目标为旧城派人数低于中阶阈值。 | 第六批补表 | 旧城派承诺 | 代码窗暂定实现值 / 测试窗必测 | 系统内部 | 奖惩以第六批补表覆盖第五批临时接口。 |
  
   
⸻  
   
## 14_Deprecated / 作废旧口径  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------------------- | ---------- | ----- | --------------------------------------------------------------- | ------------------- | ---------- | ----- | ---- | -------------------- |
| deprecated.event.auto_execute_command | Deprecated | 旧机制口径 | 事件自动执行 furnace / overload / woodfuel / ration / workers / heat。 | Patch 007-1 / 007-2 | 作废旧口径 | 作废旧口径 | 系统内部 | 事件只能提示命令或提供一次性临时效果。 |
| deprecated.event.suppressed_hidden_result | Deprecated | 旧机制口径 | 被压下的事件偷偷结算。 | Patch 007-1 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.promise.continuous_buff | Deprecated | 旧机制口径 | 承诺任务每天提高信任或降低恐慌。 | Patch 007-3 | 作废旧口径 | 作废旧口径 | 系统内部 | 承诺是限时目标，不是持续增益。 |
| deprecated.promise.free_cancel | Deprecated | 旧机制口径 | 承诺任务可以无代价取消。 | Patch 007-3 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.promise.direct_death | Deprecated | 旧机制口径 | 承诺失败直接造成死亡或秒杀玩家。 | Patch 007-1 / 007-3 | 作废旧口径 | 作废旧口径 | 系统内部 | 后果必须通过既有系统继续结算。 |
| deprecated.old_city.float_trigger | Deprecated | 旧触发口径 | 旧城派在第 22～28 天浮动触发。 | Patch 007-1 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式为第 24 天固定触发。 |
| deprecated.old_city.promise_direct_exodus | Deprecated | 旧机制口径 | 旧城派承诺失败直接触发最终出走或直接扣人口。 | Patch 007-1 / 第六批补表 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.old_city.normal_option_locks_route | Deprecated | 旧机制口径 | 公开说明锁定誓言路线 / 加强巡查锁定铁腕路线。 | Patch 007-1 | 作废旧口径 | 作废旧口径 | 系统内部 | 普通沟通 / 巡查选项不锁路线。 |
| deprecated.route.require_core_building | Deprecated | 旧路线接口 | 对应核心建筑已建成并运行。 | Patch 007 旧正文；全局总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式使用“对应路线承接物已启用并运行”。 |
| deprecated.arrival.manual_count | Deprecated | 旧机制口径 | 玩家手动输入接纳人数。 | Patch 007-1 | 固定增员 V1 不做 | 作废旧口径 | 系统内部 |  |
| deprecated.arrival.auto_assign_workers | Deprecated | 旧机制口径 | 固定增员新增人口自动分配岗位。 | Patch 007-1 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.arrival.before_d24_add_old_city | Deprecated | 旧机制口径 | 第 24 天旧城派激活前，固定增员直接增加旧城派人数。 | Patch 007-1 / 第五批补表 | 作废旧口径 | 作废旧口径 | 系统内部 |  |
| deprecated.frost.random_event | Deprecated | 旧机制口径 | 第七霜落是单日随机事件。 | 总控 / Patch 007-3 | 作废旧口径 | 作废旧口径 | 系统内部 | 正式为第 49～55 天固定终局阶段。 |
| deprecated.cold_house.cooldown_5 | Deprecated | 旧冷却值 | 寒屋之夜冷却 5 天。 | Patch 007-2；第五批补表 | 冷却覆盖 | 作废旧口径 | 系统内部 | 最新暂定实现值为 4 天。 |
  
   
⸻  
   
## 15_TODO_TEXT / 本轮仍未封存正文  
**本节仅为缺失文案汇总索引，不构成第二份文案资产记录，不进入 runtime 文案库；正式记录仍以前文首次出现位置为准。**  

| 缺失 text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------ | -------------------- | ------ | --------- | ----------- | --------- | --------- | ---- | -------- |
| event.long_shift_collapse.body | Event / Labor | 事件正文 | TODO_TEXT | Patch 007-2 | 长班后的倒下 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| event.overtime_empty_post.body | Event / Labor | 事件正文 | TODO_TEXT | Patch 007-2 | 加班后的空位 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| old_city.event.southern_letter.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 南方来信 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| old_city.event.hidden_rumors.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 暗中传言 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| old_city.event.public_gathering.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 公开集结 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| old_city.event.exodus_countdown.body | OldCity / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 离城倒计时 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| arrival.day6.body | FixedArrival / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 早期求生者 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| arrival.day19.body | FixedArrival / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 中期工程残队 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| arrival.day37.body | FixedArrival / Event | 事件正文 | TODO_TEXT | Patch 007-1 | 后期难民潮 | TODO_TEXT | 玩家可见 | 正文未封存。 |
| event.seventh_frost_start.body | FrostWarning / Event | 事件正文 | TODO_TEXT | Patch 007-3 | 第七霜落开始 | TODO_TEXT | 玩家可见 | 完整正文未封存。 |
| promise.success.title | Promise / Feedback | 成功结算标题 | TODO_TEXT | Patch 007-3 | 承诺成功 | TODO_TEXT | 玩家可见 |  |
| promise.failure.title | Promise / Feedback | 失败结算标题 | TODO_TEXT | Patch 007-3 | 承诺失败 | TODO_TEXT | 玩家可见 |  |
  
本轮已审：event.option.unavailable.feedback 与 promise.same_type.active 已恢复为 TODO_TEXT，没有把未封存提示自行写成正式文案；死亡处理提示已统一为“社会适配炉律”；普通承诺限制已拆为“自第 49 天起不再新开”与“第 42 天后截止日压至第 48 天”两条；TODO 汇总区已改为非 runtime 索引，不再构成重复资产记录；系统内部条目统一不进入正式 TextRegistry。  
