**第 1 轮 命名规则 / UI / 面板氛围 / 资源 / 状态 / 天气 / 基础命令**  
  
开发注释，不进入 runtime text_id；如后续需要玩家可见说明，另建 help/status 文案。  
  
## 命名规则  

| 类别 | 命名规则 |
| --- | ----------------------------------------------------------------------------------------------- |
| UI | ui.xxx.title / ui.xxx.label / ui.xxx.flavor |
| 资源 | resource.xxx.name / resource.xxx.desc |
| 状态 | status.xxx.name / status.xxx.desc / status.xxx.warning |
| 天气 | weather.xxx.name / weather.xxx.desc / weather.xxx.warning |
| 温度 | temperature.xxx.label / temperature.xxx.tip |
| 炉心 | furnace.xxx.name / furnace.xxx.desc |
| 命令 | command.xxx.name / command.xxx.desc / command.xxx.format |
| 行动 | action.xxx.name / action.xxx.confirm / action.xxx.success / action.xxx.fail |
| 确认框 | confirm.xxx.body |
| 事件 | event.xxx.title / event.xxx.body / event.xxx.option_a / event.xxx.option_b / event.xxx.option_c |
| 承诺 | promise.xxx.title / promise.xxx.desc / promise.xxx.success / promise.xxx.fail |
| 终局 | ending.xxx.tag / ending.xxx.report_line |
  
   
⸻  
   
## 01_UI / 基础显示  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------ | ------------ | ------ | -------- | ---------------------------- | ---------------------- | ----- | ---- | ------------------- |
| ui.game.title | UI | 游戏名 | 炉心残冬 | Patch 001 | 游戏基础定位 | 已封存原文 | 通用 |  |
| ui.game.length | UI | 游戏长度显示 | 55 个寒冬日夜 | Patch 001 | 游戏基础定位 | 已封存原文 | 玩家可见 | 该数值为封存展示文案。 |
| ui.disaster.seventh_frost.name | UI / Weather | 终局灾害名 | 第七霜落 | Patch 001；Patch 005；总控；第七批补表 | 游戏基础定位 / 天气类型 / 第七霜落口径 | 已封存原文 | 通用 | 第七霜落不是额外 hard_fail。 |
| ui.player.role | UI | 玩家身份 | 执政官 | Patch 001 | 游戏基础定位 | 已封存原文 | 玩家可见 |  |
| ui.panel.status.title | UI | 面板名 | status | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| ui.panel.city.title | UI | 面板名 | city | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| ui.panel.laws.title | UI | 面板名 | laws | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| ui.panel.tech.title | UI | 面板名 | tech | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| ui.panel.workers.title | UI | 面板名 | workers | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| ui.panel.help.title | UI | 面板名 | help | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
  
   
⸻  
   
## 02_UI / 面板氛围文案  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------------- | ------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------------------- | ----- | ---- | ---------------------- |
| ui.panel.status.flavor | UI | 面板氛围 | 炉心井还在烧，但它的光根本照不到每一张脸。有人挤在热管旁发抖，有人在病床上叹息，而你的抉择将决定今天先救煤，还是先救人。 | Patch 004 | 面板氛围文案 / status 面板 | 已封存原文 | 玩家可见 |  |
| ui.panel.city.flavor | UI | 面板氛围 | 城市像一圈圈冻裂的伤口，内环还残留炉心余温，外环却已被风雪啃得发白。每一座新建筑都像是在问：谁值得占据这仅剩的热量？ | Patch 004 | 面板氛围文案 / city 面板 | 已封存原文 | 玩家可见 |  |
| ui.panel.laws.flavor | UI | 面板氛围 | 誓约碑前没有人高声争辩，只有冻僵的手印留在铁板边缘。每一条炉律都不是答案，只是把某些人的绝望与痛苦写得更像秩序。 | Patch 004 | 面板氛围文案 / laws 面板 | 已封存原文 | 玩家可见 |  |
| ui.panel.tech.flavor | UI | 面板氛围 | 研究所的灯亮到深夜，工程师们用冻裂的嘴唇低声争执。他们不是在追求进步，只是在和死亡讨价还价，试图把明天争回来一些。 | Patch 004 | 面板氛围文案 / tech 面板 | 已封存原文 | 玩家可见 |  |
| ui.panel.workers.flavor | UI | 面板氛围 | 分工牌上有些名字被划掉，又有新的名字挤上去；炉城已经没有多余的铁做新工牌。所以能站起来的人，哪怕还在咳血，也会被写进今日的岗位。 | Patch 004 | 面板氛围文案 / workers 面板 | 已封存原文 | 玩家可见 |  |
| ui.end_day.before.flavor | UI | 结算前氛围 | 夜晚压过来，炉城的边界被风雪一点点抹掉。若现在结束这一天，所有没来得及处理的寒冷、饥饿和病痛，都会替你做出选择。 | Patch 004 | 面板氛围文案 / end_day 结算前 | 已封存原文 | 玩家可见 |  |
| ui.end_day.after.flavor | UI | 结算后氛围 | 清晨没有真正到来，只是黑夜变薄了一点。炉心还亮着，但名单上少了几个人；活下来的人没有欢呼或哀悼的力气，只是继续排队领今天那一点微薄的热量。 | Patch 004 | 面板氛围文案 / end_day 结算后 | 已封存原文 | 玩家可见 |  |
| ui.hunting_area_found.flavor | UI / Hunting | 特殊提示氛围 | 风雪里有一抹白影一闪而过，像冬天最后舍不得熄灭的火。猎人说，那是雪狐——皱巴巴、圆滚滚、还活着的白色小东西，也是这片冻土上最后一部分仍能奔跑的生命。它们可以成为食物，也可以成为火种。只是炉城里的锅已经见底，而孩子们还在排队。 | Patch 004 | 面板氛围文案 / 狩猎区发现时 | 已封存原文 | 玩家可见 | 仅作为特殊提示，不作为事件正文。 |
| ui.warning.low_trust.flavor | UI / Warning | 特殊状态氛围 | 人们仍然听从命令，但不再抬头看你。炉心的光还在城中摇晃，可他们已经开始怀疑，自己究竟是在被守护，还是被消耗。 | Patch 004 | 面板氛围文案 / 信任过低时 | 已封存原文 | 玩家可见 | 仅作为 status 提示，不进入终局文案。 |
| ui.warning.high_panic.flavor | UI / Warning | 特殊状态氛围 | 风雪还没有冲进城里，恐惧已经先压进人群。有人囤食，有人拒绝上工，有人在夜里高喊：如果明天注定要死，今天为什么还要服从？ | Patch 004 | 面板氛围文案 / 恐慌过高时 | 已封存原文 | 玩家可见 | 仅作为 status 提示，不进入终局文案。 |
| ui.warning.low_coal.flavor | UI / Warning | 特殊状态氛围 | 煤堆低得像一句快要说完的谎言。炉心仍在索要燃料，而仓库里仅剩的黑色碎块，已经在给睡梦里的人设计墓碑。 | Patch 004 | 面板氛围文案 / 煤炭不足时 | 已封存原文 | 玩家可见 |  |
| ui.warning.low_food.flavor | UI / Warning | 特殊状态氛围 | 食堂排队的人比昨天更安静。没人再抱怨份量，因为每个人都看见了锅底，也看见了排在自己身后的孩子。 | Patch 004 | 面板氛围文案 / 食物不足时 | 已封存原文 | 玩家可见 |  |
| ui.warning.medical_collapse.flavor | UI / Warning | 特殊状态氛围 | 医疗站里没有足够的床，也没有足够的热。病人被分成“还能等”和“等不了”，而医生只能说服自己这种区别不是判决。 | Patch 004 | 面板氛围文案 / 医疗崩溃时 | 已封存原文 | 玩家可见 |  |
| ui.warning.furnace_off.flavor | UI / Warning | 特殊状态氛围 | 炉心沉默下去的那一刻，整座城都像屏住了呼吸。寒冷不会说话，它只是走进每一间屋子，而风声像死亡的悼词。 | Patch 004 | 面板氛围文案 / 炉心关闭时 | 已封存原文 | 玩家可见 |  |
| ui.warning.overload.flavor | UI / Warning | 特殊状态氛围 | 炉心发出近乎痛苦的轰鸣，像一颗被迫继续跳动的心脏。人们感到一丝久违的暖意，却没人知道这份暖意会烧掉多少明天。 | Patch 004 | 面板氛围文案 / 开启过载时 | 已封存原文 | 玩家可见 |  |
| ui.warning.woodfuel.flavor | UI / Warning | 特殊状态氛围 | 木材被推进炉膛，火光短暂亮起来。有人看着那些本该变成房梁、病床和采集棚的木料化成灰，眼神木然得像已经没有力气判断这是不是正确。 | Patch 004 | 面板氛围文案 / 启用木材应急燃烧时 | 已封存原文 | 玩家可见 |  |
| ui.warning.homeless.flavor | UI / Warning | 特殊状态氛围 | 有些人没有床位，只能靠在炉心边等天亮。炉城仍说自己庇护着所有人，但风知道，今晚并不是每个人都有屋顶。 | Patch 004 | 面板氛围文案 / 无住所人口出现时 | 已封存原文 | 玩家可见 |  |
| ui.warning.child_protection_low.flavor | UI / Warning | 特殊状态氛围 | 孩子们被安置在离炉心最近的角落，却仍然有人冻醒。大人们把仅剩的布盖在他们身上，然后转身去冰冷的工作地继续拼命干活。 | Patch 004 | 面板氛围文案 / 儿童保护不足时 | 已封存原文 | 玩家可见 |  |
| ui.warning.child_helper_enabled.flavor | UI / Warning | 特殊状态氛围 | 孩子们被领到工地边缘，手套比他们的手大，工具比他们的胳膊沉。有人说这不是残忍，是活下去；可当第一个孩子学会沉默地低头搬煤时，炉城就已经失去了一些东西。 | Patch 004 | 面板氛围文案 / 儿童辅工启用时 | 已封存原文 | 玩家可见 |  |
| ui.warning.apprentice_enabled.flavor | UI / Warning | 特殊状态氛围 | 学堂的炉火很小，照不亮整间屋子，但孩子们仍围在图纸和工具旁学习。大人们说他们是在为明天准备，可每个人都知道，所谓明天，只是今天还没有吞掉的那一部分孩子。 | Patch 004 | 面板氛围文案 / 学徒制度启用时 | 已封存原文 | 玩家可见 |  |
| ui.warning.cemetery_built.flavor | UI / Warning | 特殊状态氛围 | 墓园并没有让死亡有意义，只是让死亡有了位置。活人能分到多一口食物，而炉城也终于有了一个地方，安放那些没撑到春天的人。 | Patch 004 | 面板氛围文案 / 墓园建成时 | 已封存原文 | 玩家可见 |  |
| ui.warning.temporary_overflow.flavor | UI / Warning | 特殊状态氛围 | 仓库被塞得满满当当，门缝都挤着求生的重量。可这些物资不是富余，只是另一种混乱；城市已经连保存希望都显得狼狈。 | Patch 004 | 面板氛围文案 / 临时超仓时 | 已封存原文 | 玩家可见 |  |
| ui.warning.seventh_frost_near.flavor | UI / Warning | 终局临近氛围 | 风声变了，像有什么巨大的东西正在雪幕后靠近。炉城里所有人都明白，之前的寒冷只是练习，真正的审判即将逼近。谁有资格活过明天？是谁规定的？谁会被寒冬巨兽无情吞没？又是谁允许这一切继续发生？炉心仍在燃烧，可人性、火种、希望这些词，已经轻得像雪。明天还会到来吗？如果会，那里还会有人吗？ | Patch 004 | 面板氛围文案 / 第七霜落临近时 | 已封存原文 | 玩家可见 | 第七霜落不是额外 hard_fail。 |
  
   
⸻  
   
## 03_Resource / 资源与资源系统  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------------- | ------------------ | ----- | ------ | -------------------------- | -------------------- | ------- | ---- | ------------------------- |
| resource.coal.name | Resource | 资源名 | 煤炭 | Patch 003 | 核心资源种类 | 已封存原文 | 通用 |  |
| resource.wood.name | Resource | 资源名 | 木材 | Patch 003 | 核心资源种类 | 已封存原文 | 通用 |  |
| resource.steel.name | Resource | 资源名 | 钢铁 | Patch 003 | 核心资源种类 | 已封存原文 | 通用 |  |
| resource.raw_food.name | Resource | 资源名 | 生食 | Patch 003 | 核心资源种类 | 已封存原文 | 通用 |  |
| resource.cooked_food.name | Resource | 资源名 | 熟食 | Patch 003 | 核心资源种类 | 已封存原文 | 通用 |  |
| resource.scattered_steel.name | Resource | 资源名 | 散落钢铁 | 总控 / 全局修正 / 七批补表 | 正式命名校对 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。 |
| resource.food.display | Resource | 显示口径 | 食物显示口径 | Patch 003 | 生食与熟食规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| resource.food.priority | Resource | 规则提示 | 熟食优先 | Patch 003 | 生食与熟食规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| resource.raw_food.consequence | Resource | 规则提示 | 生食后果 | Patch 003 | 生食与熟食规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| resource.storage.name | Resource / Storage | 系统名 | 仓储系统 | Patch 003 | 仓储系统 | 已封存原文 | 通用 |  |
| resource.storage.overflow.name | Resource / Storage | 状态名 | 爆仓规则 | Patch 003 | 爆仓规则 | 已封存原文 | 系统内部 | 如 UI 明确显示“爆仓”，可另建玩家可见状态名。 |
| resource.storage.temporary_overflow.name | Resource / Storage | 状态名 | 临时超仓 | Patch 003 / Patch 004 | 爆仓规则 / 临时超仓时 | 已封存原文 | 通用 |  |
| resource.surface_coal.name | Resource / Map | 地表资源名 | 地表小型煤堆 | Patch 002-A / Patch 006B-3 | 前期采集点与避寒采集棚 / 资源采集科技 | 已封存原文 | 通用 |  |
| resource.surface_wood.name | Resource / Map | 地表资源名 | 木材堆 | Patch 002-A / Patch 006B-3 | 前期采集点与避寒采集棚 / 资源采集科技 | 已封存原文 | 通用 |  |
| resource.surface_steel.name | Resource / Map | 地表资源名 | 钢铁堆 | Patch 002-A / Patch 006B-3 | 前期采集点与避寒采集棚 / 资源采集科技 | 已封存原文 | 待判定 | 正式钢铁类命名需按“散落钢铁”校对。 |
  
补充：resource.scattered_coal.name | Resource / Map | 地表资源名 | 散落煤炭 | 总控 / 全局修正 | 正式命名校对 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。  
resource.scattered_wood.name | Resource / Map | 地表资源名 | 散落木材 | 总控 / 全局修正 | 正式命名校对 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。  
resource.scattered_steel.name | Resource / Map | 地表资源名 | 散落钢铁 | 总控 / 全局修正 | 正式命名校对 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。  
  
地图资源点旧封存表述；正式 UI 显示优先使用 scattered_* 命名。   
⸻  
   
## 04_Status / 状态字段与状态名  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| --------------------------------- | ------------------- | ---- | --------- | -------------- | ------------- | ------- | --- | ---------- |
| status.trust.name | Status | 正式字段 | 信任 | Patch 002-B；总控 | 情绪系统 / 全局正式字段 | 用户确认覆盖项 | 通用 | 正式字段使用：信任。 |
| status.panic.name | Status | 正式字段 | 恐慌 | Patch 002-B；总控 | 情绪系统 / 全局正式字段 | 用户确认覆盖项 | 通用 | 正式字段使用：恐慌。 |
| status.healthy.name | Status / Population | 人口状态 | 健康 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.sick.name | Status / Population | 人口状态 | 患病 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.critical.name | Status / Population | 人口状态 | 重症 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.frostbite.name | Status / Population | 人口状态 | 冻伤 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.disabled.name | Status / Population | 人口状态 | 伤残 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.dead.name | Status / Population | 人口状态 | 死亡 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.hunger.name | Status | 状态名 | 饥饿 | Patch 003 | 饥饿规则 | 已封存原文 | 通用 |  |
| status.starving.name | Status | 状态名 | 濒饿 | Patch 003 | 饥饿规则 | 已封存原文 | 通用 | 已修正上一版误写。 |
| status.hunger_death.name | Status | 状态名 | 饥饿死亡 | Patch 003 | 饥饿死亡 | 已封存原文 | 通用 |  |
| status.cold_exposure.name | Status / Weather | 状态名 | 寒冷暴露 | Patch 005 | 寒冷暴露机制 | 已封存原文 | 通用 |  |
| status.cold_exposure.level_0.name | Status / Weather | 暴露等级 | 等级 0：安全 | Patch 005 | 寒冷暴露等级 | 已封存原文 | 通用 |  |
| status.cold_exposure.level_1.name | Status / Weather | 暴露等级 | 等级 1：轻度暴露 | Patch 005 | 寒冷暴露等级 | 已封存原文 | 通用 |  |
| status.cold_exposure.level_2.name | Status / Weather | 暴露等级 | 等级 2：中度暴露 | Patch 005 | 寒冷暴露等级 | 已封存原文 | 通用 |  |
| status.cold_exposure.level_3.name | Status / Weather | 暴露等级 | 等级 3：重度暴露 | Patch 005 | 寒冷暴露等级 | 已封存原文 | 通用 |  |
| status.cold_exposure.level_4.name | Status / Weather | 暴露等级 | 等级 4：灾害暴露 | Patch 005 | 寒冷暴露等级 | 已封存原文 | 通用 |  |
| status.cold_exposure.level_5.name | Status / Weather | 暴露等级 | 等级 5：终局暴露 | Patch 005 | 寒冷暴露等级 | 已封存原文 | 通用 |  |
  
   
⸻  
   
## 05_Weather / 天气与温度  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------------- | ----------- | ----- | ---------------------- | ------------------ | ------------- | ----- | ---- | ------------------- |
| weather.system.desc | Weather | 系统说明 | 《炉心残冬》的天气不是背景板，而是主要敌人。 | Patch 005 | 天气系统核心原则 | 已封存原文 | 系统内部 | 可作为设计口径，不直接给玩家显示。 |
| weather.residual_warmth.name | Weather | 天气名 | 残暖 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.cold_wind.name | Weather | 天气名 | 寒风 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.cooling.name | Weather | 天气名 | 降温 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.cold_wave.name | Weather | 天气名 | 寒潮 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.blizzard.name | Weather | 天气名 | 暴雪 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.extreme_cold.name | Weather | 天气名 | 极寒 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.black_frost.name | Weather | 天气名 | 黑霜 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.false_warming.name | Weather | 天气名 | 假性回温 | Patch 005 | 天气类型 | 已封存原文 | 通用 |  |
| weather.seventh_frost.name | Weather | 天气名 | 第七霜落 | Patch 005；总控；第七批补表 | 天气类型 / 终局口径 | 已封存原文 | 通用 | 第七霜落不是额外 hard_fail。 |
| temperature.base.label | Temperature | UI 标签 | 基础温度 | Patch 005 | 显示方式 | 已封存原文 | 通用 |  |
| temperature.effective.label | Temperature | UI 标签 | 有效温度 | Patch 005 | 显示方式 | 已封存原文 | 通用 |  |
| weather.forecast.tomorrow.label | Weather | UI 标签 | 明日预报 | Patch 005 | 天气预报机制 / 显示方式 | 已封存原文 | 通用 |  |
| weather.forecast.three_day_trend.label | Weather | UI 标签 | 三日趋势 | Patch 005 | 天气预报机制 / 显示方式 | 已封存原文 | 通用 |  |
| weather.warning.main.label | Weather | UI 标签 | 主要天气预警 | Patch 005 | 显示方式 | 已封存原文 | 通用 |  |
| weather.warning.tomorrow.label | Weather | UI 标签 | 明日预警： | Patch 005 | 停工预警 | 已封存原文 | 通用 | 仅作为面板提示格式，不作为事件正文。 |
  
  
终局机制口径由总控 / 第七批补表覆盖：第七霜落不是额外 hard_fail。   
⸻  
   
## 06_Command / 基础命令  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------- | ------- | ---- | --------------------- | ----------------------- | ------------------ | ------- | ---- | ----------------------------- |
| command.status.name | Command | 命令名 | status | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| command.status.desc | Command | 命令说明 | 查看城市总览。 | Patch 004 | 基础面板命令 / status | 已封存原文 | 玩家可见 |  |
| command.city.name | Command | 命令名 | city | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| command.city.desc | Command | 命令说明 | 查看城市建筑、区域槽位、资源点和工作状态。 | Patch 004 | 基础面板命令 / city | 已封存原文 | 玩家可见 |  |
| command.laws.name | Command | 命令名 | laws | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| command.laws.desc | Command | 命令说明 | 查看城约 / 炉律状态。 | Patch 004 | 基础面板命令 / laws | 已封存原文 | 玩家可见 |  |
| command.tech.name | Command | 命令名 | tech | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| command.tech.desc | Command | 命令说明 | 查看科技状态。 | Patch 004 | 基础面板命令 / tech | 已封存原文 | 玩家可见 |  |
| command.workers.name | Command | 命令名 | workers | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| command.workers.desc | Command | 命令说明 | 查看人手分配概况。 | Patch 004 | 基础面板命令 / workers | 已封存原文 | 玩家可见 |  |
| command.help.name | Command | 命令名 | help | Patch 004 | 基础面板命令 | 已封存原文 | 通用 |  |
| command.help.desc | Command | 命令说明 | 查看可用命令说明。 | Patch 004 | 基础面板命令 / help | 已封存原文 | 玩家可见 |  |
| command.build.name | Command | 命令名 | build | Patch 004 | 建造命令 | 已封存原文 | 通用 |  |
| command.build.desc | Command | 命令说明 | 建造建筑。 | Patch 004 | 建造命令 / build | 已封存原文 | 玩家可见 |  |
| command.build.format | Command | 命令格式 | build <建筑名> <区域> | Patch 004 | 建造命令 / build | 已封存原文 | 通用 |  |
| command.demolish.name | Command | 命令名 | demolish | Patch 004 | 拆除命令 | 已封存原文 | 通用 |  |
| command.confirm.name | Command | 命令名 | confirm | Patch 004 | 确认命令 | 已封存原文 | 通用 |  |
| command.assign.name | Command | 命令名 | assign | Patch 004 | 人手分配命令 | 已封存原文 | 通用 |  |
| command.unassign.name | Command | 命令名 | unassign | Patch 004 | 人手分配命令 | 已封存原文 | 通用 |  |
| command.furnace.name | Command | 命令名 | furnace | Patch 004 | 炉心命令 | 已封存原文 | 通用 |  |
| command.overload.name | Command | 命令名 | overload | Patch 004 | 过载命令 | 已封存原文 | 通用 |  |
| command.heat.name | Command | 命令名 | heat | Patch 004；总控；006B 修正复核包 | 应急加热命令 / heat 开局可用 | 用户确认覆盖项 | 通用 | heat 开局可用；应急加热装置不是 heat 解锁科技。 |
| command.woodfuel.name | Command | 命令名 | woodfuel | Patch 004 | 木材应急燃烧命令 | 已封存原文 | 通用 |  |
| command.research.name | Command | 命令名 | research | Patch 004 / 006B | 研究命令 / 研究系统 | 已封存原文 | 通用 |  |
| command.cancel_research.name | Command | 命令名 | cancel research | Patch 004 / 006B | 研究命令 | 已封存原文 | 通用 |  |
| command.sign.name | Command | 命令名 | sign | Patch 004 / 006A / 006C | 城约命令入口 | 已封存原文 | 通用 |  |
| command.ration.name | Command | 命令名 | ration | Patch 004 / 006A-4 | 食物与配给命令入口 | 已封存原文 | 通用 |  |
| command.end_day.name | Command | 命令名 | end_day | Patch 004 | 结束一天命令 | 已封存原文 | 通用 |  |
  
   
⸻  
   
## 07_Warning / 预警等级与内部等级说明  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------- | ------- | ---- | ------------- | --------------------- | ------------------- | ----- | ---- | --------------------------- |
| warning.level.info.name | Warning | 预警等级 | A 信息提示 | Patch 001 / Patch 005 | end_day 预警分级 / 停工预警 | 已封存原文 | 待判定 | 若 UI 显示 A/B/C 则玩家可见；否则系统内部。 |
| warning.level.strong.name | Warning | 预警等级 | B 强警告 | Patch 001 / Patch 005 | end_day 预警分级 / 停工预警 | 已封存原文 | 待判定 | 若 UI 显示 A/B/C 则玩家可见；否则系统内部。 |
| warning.level.block.name | Warning | 预警等级 | C 硬阻塞 | Patch 001 / Patch 005 | end_day 预警分级 / 停工预警 | 已封存原文 | 待判定 | 若 UI 显示 A/B/C 则玩家可见；否则系统内部。 |
| warning.level.info.desc | Warning | 预警说明 | 不阻塞 | Patch 005 | 停工预警 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| warning.level.strong.desc | Warning | 预警说明 | 需要 confirm | Patch 005 | 停工预警 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| warning.level.block.desc | Warning | 预警说明 | 必须处理或二次确认特殊命令 | Patch 005 | 停工预警 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
  
   
⸻  
   
## 08_作废旧口径 / 仅排查，不导正式玩家文案  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------ | ---------- | ---- | ------------- | --------------- | -------------- | ----- | ---- | ------------------------- |
| deprecated.status.hope | Deprecated | 旧字段 | 希望 | 总控 / 全局修正 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.status.oppression | Deprecated | 旧字段 | 压迫 | 总控 / 全局修正 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.status.dissatisfaction | Deprecated | 旧字段 | 不满 | Patch 002-B；总控 | 情绪系统命名 / 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.status.hope_state | Deprecated | 旧字段 | hope_state | 总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.status.trust_fail | Deprecated | 旧字段 | trust_fail | 总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.status.panic_fail | Deprecated | 旧字段 | panic_fail | 总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.ending.terminal_fail | Deprecated | 旧字段 | terminal_fail | 总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.region.edge | Deprecated | 旧区域 | 边缘区 | Patch 002-A；总控 | 区域结构 | 作废旧口径 | 系统内部 | 边缘区只作为外环显示别名，不作为独立代码区域字段。 |
| deprecated.building.workshop | Deprecated | 旧建筑名 | 修造工坊 / 工坊 | 总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.tech.outer_cold_equipment | Deprecated | 旧科技名 | 外环防寒装备 | 总控 / 006B 修正复核包 | 正式命名覆盖 | 作废旧口径 | 系统内部 | 正式名为“外勤防寒装备”。 |
  
  
补充作废口径：deprecated.resource.scattered_food | Deprecated | 旧资源点 | 散落食物点 | 总控 / 全局修正 | 作废旧口径 | 作废旧口径 | 系统内部 | V1 不设置散落食物点，食物来源为狩猎小屋 / 温室 / 固定事件 / 开局储备。   
  
