# 第 2 轮：建筑 / Facility / 地图资源点 / 炉心 / heat / 仓储 / 医疗  
## 01_Region / 区域与槽位显示名  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------ | ------------ | ---- | ----- | -------------- | -------------- | ----- | ---- | ------------------------- |
| region.inner.name | Region | 区域名 | 内环 | Patch 002-C | 城市空间结构 | 已封存原文 | 通用 |  |
| region.middle.name | Region | 区域名 | 中环 | Patch 002-C | 城市空间结构 | 已封存原文 | 通用 |  |
| region.outer.name | Region | 区域名 | 外环 | Patch 002-C | 城市空间结构 | 已封存原文 | 通用 |  |
| region.storage_edge.name | Region | 区域名 | 外缘储放区 | Patch 002-C | 城市空间结构 | 已封存原文 | 通用 |  |
| region.edge_alias.name | Region | 显示别名 | 边缘区 | Patch 002-C；总控 | 城市空间结构 / 作废旧口径 | 作废旧口径 | 系统内部 | 边缘区只作为外环显示别名，不作为独立代码区域字段。 |
| slot.small.name | BuildingSlot | 槽位类型 | 小型建筑 | Patch 002-C | 建筑占地等级 | 已封存原文 | 通用 |  |
| slot.medium.name | BuildingSlot | 槽位类型 | 中型建筑 | Patch 002-C | 建筑占地等级 | 已封存原文 | 通用 |  |
| slot.large.name | BuildingSlot | 槽位类型 | 大型建筑 | Patch 002-C | 建筑占地等级 | 已封存原文 | 通用 |  |
  
   
⸻  
   
## 02_Building / 基础与生活建筑  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| -------------------------------- | ------------------ | ------ | ------------------------------------ | -------------------------- | ---------------- | ------- | ---- | --------------------- |
| building.house_basic.name | Building | 建筑名 | 基础住宅 | Patch 002-C / 006B-4 | 住宅建筑 / 住房科技 | 已封存原文 | 通用 |  |
| building.house_basic.desc | Building | 建筑说明 | 基础住宅开局可建。 | Patch 006B-4 | 基础建筑边界 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.house_improved.name | Building | 建筑名 | 改良住宅 | Patch 002-C / 006B-4 | 住宅升级 | 已封存原文 | 通用 |  |
| building.house_advanced.name | Building | 建筑名 | 高级住宅 | Patch 006B-4 | 高级住宅标准 | 已封存原文 | 通用 |  |
| building.house.heat_rule | Building / Heat | 建筑规则提示 | 住宅仍不可使用 heat。 | Patch 006B-4；总控 | 改良住宅标准 / heat 口径 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.canteen.name | Building | 建筑名 | 食堂 | Patch 002-C / 006B-4 | 建筑占槽 / 基础建筑边界 | 已封存原文 | 通用 |  |
| building.canteen.desc | Building | 建筑说明 | 食堂是全城配餐、热食加工与配给秩序建筑，不作为可无限铺设的小厨房处理。 | Patch 002-C | 食堂规则 | 已封存原文 | 待判定 | 可作玩家说明，也可作系统口径。 |
| building.child_shelter.name | Building | 建筑名 | 儿童保护所 | Patch 002-C / 006A | 建筑占槽 / 儿童保护 | 已封存原文 | 通用 |  |
| building.school.name | Building | 建筑名 | 学堂 | Patch 002-A / 002-C / 006A | 学堂规则 / 建筑占槽 | 已封存原文 | 通用 |  |
| building.school.temperature_rule | Building / Weather | 建筑规则提示 | 学堂属于准关键建筑，温度不足时停课，不能产生医疗学徒 / 工程学徒效果。 | Patch 002-A | 学堂口径修正 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.tavern.name | Building | 建筑名 | 小酒馆 | 总控 / 全局修正 | 正式命名校对 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。 |
| building.casino.name | Building | 建筑名 | 大赌场 | 总控 / 全局修正 | 正式命名校对 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。 |
  
   
⸻  
   
## 03_Building / 医疗建筑  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------ | ------------------ | ------ | ---------------------------------- | ---------------------------- | ---------------- | ------- | ---- | --------------------- |
| building.medical_station.name | Building / Medical | 建筑名 | 医疗站 | Patch 002-A / 002-C / 006B-4 | 医疗建筑 / 基础建筑边界 | 已封存原文 | 通用 |  |
| building.medical_station.unlock_rule | Building / Medical | 解锁提示 | 医疗站由 006A 的基础医疗法解锁，不由工程科技解锁。 | Patch 006B-4；全局解锁索引 | 基础建筑边界 | 用户确认覆盖项 | 系统内部 | 正文按 A 干净封存版，命名按七批补表。 |
| building.hospital.name | Building / Medical | 建筑名 | 医院 | Patch 002-A / 002-C / 006B-4 | 医疗建筑 / 医院标准化 | 已封存原文 | 通用 |  |
| building.hospital.desc | Building / Medical | 建筑说明 | 医院容量大、保温更好、结构复杂，是中后期核心医疗建筑。 | Patch 002-C | 大型建筑 / 医院 | 已封存原文 | 待判定 | 可作玩家说明，也可作系统口径。 |
| building.hospital.unlock_rule | Building / Medical | 解锁提示 | 建造医院需要已签署基础医疗法，并已完成医院标准化科技。二者缺一不可。 | Patch 006B-4 | 医院标准化 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.care_home.name | Building / Medical | 建筑名 | 养护所 | Patch 006B-4 | 医疗建筑保温 | 已封存原文 | 通用 |  |
| building.care_home.rule | Building / Medical | 建筑规则提示 | 养护所只获得保温与护理风险降低收益。 | Patch 006B-4 | 医疗建筑保温 / 养护所特殊口径 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.care_home.not_treatment | Building / Medical | 建筑规则提示 | 养护所不因此变成医疗站 / 医院类治疗建筑。 | Patch 006B-4 | 医疗建筑保温 / 养护所特殊口径 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
  
   
⸻  
   
## 04_Building / 食物与资源建筑  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------------- | ------------------- | ------ | ------------------------------------ | ------------------------------- | --------------- | ------- | ---- | ----------------------------------------------------------- |
| building.hunting_lodge.name | Building / Food | 建筑名 | 狩猎小屋 | Patch 002-A / 002-C / 006B-4 | 狩猎小屋规则 / 基础建筑边界 | 已封存原文 | 通用 |  |
| building.hunting_lodge.desc | Building / Food | 建筑说明 | 狩猎小屋包含休整、工具、猎物处理和出猎准备空间，不作为 1 槽小屋处理。 | Patch 002-C | 狩猎小屋 | 已封存原文 | 待判定 | 可作玩家说明，也可作系统口径。 |
| building.hunting_lodge.limit_rule | Building / Food | 建筑规则提示 | 狩猎小屋受当前可用猎区数量限制，不能无限建造。 | Patch 002-A / 002-C | 狩猎小屋规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.greenhouse.name | Building / Food | 建筑名 | 温室 | Patch 002-A / 002-C / 006B-4 | 温室 / 温室栽培 | 已封存原文 | 通用 |  |
| building.greenhouse.desc | Building / Food | 建筑说明 | 温室需要封闭种植空间、保温结构和作物区域。 | Patch 002-C | 大型建筑 / 温室 | 已封存原文 | 待判定 | 可作玩家说明，也可作系统口径。 |
| building.greenhouse.unlock_rule | Building / Food | 解锁提示 | 温室栽培负责解锁温室建筑。 | Patch 006B-4 | 温室改良 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.greenhouse_improved.name | Building / Food | 建筑名 | 改良温室 | Patch 006B-4 | 温室改良 | 已封存原文 | 通用 |  |
| building.greenhouse_improved.unlock_rule | Building / Food | 解锁提示 | 温室改良负责解锁温室逐座升级。 | Patch 006B-4 | 温室改良 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.lumberyard.name | Building / Resource | 建筑名 | 伐木场 | Patch 002-A / 002-C / 006B-3 | 木材区 / 伐木场线 | 已封存原文 | 通用 |  |
| building.lumberyard.rule | Building / Resource | 建筑规则提示 | 伐木场必须绑定森林区建造。 | 用户补充校正；Patch 006B-3 | 木材加工 I / 伐木场线 | 用户确认覆盖项 | 系统内部 | 森林区是地图资源锚点，伐木场是绑定森林区的建筑；不使用“伐木场点”作为正式资源点名。 |
| building.small_coal_miner.name | Building / Resource | 建筑名 | 小型采煤机 | Patch 002-A / 002-C / 006B-3；总控 | 资源生产建筑 / 正式命名 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。 |
| building.small_coal_miner.rule | Building / Resource | 建筑规则提示 | 小型采煤机不需要大型煤矿点。 | Patch 006B-3 | 小型采煤机 / 小型采钢机 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.small_steel_miner.name | Building / Resource | 建筑名 | 小型采钢机 | Patch 002-A / 002-C / 006B-3；总控 | 资源生产建筑 / 正式命名 | 用户确认覆盖项 | 通用 | 该名称已由总控覆盖。 |
| building.small_steel_miner.rule | Building / Resource | 建筑规则提示 | 小型采煤机 / 小型采钢机不绑定大型矿点。 | Patch 006B-3 | 资源线口径 | 已封存原文 | 系统内部 | 全局重复过多，建议复用。 |
| building.large_coal_miner.name | Building / Resource | 建筑名 | 大型煤矿机 | Patch 002-A / 002-C / 006B-3 | 大型矿机规则 | 已封存原文 | 通用 | V1 后期建筑；完整成本 / 岗位 / 产出 / 科技细节按后续建筑 / 科技表确认，本文案表只收名称与基础绑定规则。 |
| building.large_coal_miner.rule | Building / Resource | 建筑规则提示 | 大型煤矿机只能建在大型煤矿点上。 | Patch 006B-3 | 深层煤脉开采 | 已封存原文 | 系统内部 | V1 后期建筑；完整成本 / 岗位 / 产出 / 科技细节按后续建筑 / 科技表确认，本文案表只收名称与基础绑定规则。 |
| building.large_steel_miner.name | Building / Resource | 建筑名 | 大型钢铁矿机 | Patch 002-A / 002-C / 006B-3 | 大型矿机规则 | 已封存原文 | 通用 | V1 后期建筑；完整成本 / 岗位 / 产出 / 科技细节按后续建筑 / 科技表确认，本文案表只收名称与基础绑定规则。 |
| building.large_steel_miner.rule | Building / Resource | 建筑规则提示 | 大型煤矿机和大型钢铁矿机必须绑定地图矿点。 | Patch 006B-3 | 大型矿点绑定规则 | 已封存原文 | 系统内部 | V1 后期建筑；完整成本 / 岗位 / 产出 / 科技细节按后续建筑 / 科技表确认，本文案表只收名称与基础绑定规则。 |
  
   
⸻  
   
## 05_Building / 仓储与附属设施  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------------- | ----------------------------- | ------ | ----------------------------- | ---------------------------- | ----------- | ----- | ---- | ----------------------------------------------- |
| building.core_temporary_storage.name | Building / Storage | 系统仓储名 | 炉心临时仓储点 | Patch 008-1 / 008-2 | 开局系统仓储 | 已封存原文 | 通用 | 开局系统自带基础仓储，容量 800，不占槽、不可拆、不可升级；不是小仓库，也不是大仓库。 |
| building.warehouse_small.name | Building / Storage | 建筑名 | 小仓库 / 临时储备棚 | Patch 002-C | 仓库规则 | 已封存原文 | 通用 | 小仓库 / 临时储备棚为仓储建筑，占 2 个外缘储放区槽位；不同于开局自带的炉心临时仓储点。 |
| building.warehouse_small.desc | Building / Storage | 建筑说明 | “小仓库”是相对于大仓库而言。 | Patch 002-C | 小仓库 / 临时储备棚 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.warehouse_large.name | Building / Storage | 建筑名 | 大仓库 / 深层储藏库 | Patch 002-C | 仓库规则 | 已封存原文 | 通用 | 大仓库 / 深层储藏库为大型仓储建筑，占 3 个外缘储放区槽位；与小仓库、炉心临时仓储点区分。 |
| building.warehouse_large.desc | Building / Storage | 建筑说明 | 大仓库提供大量容量，因此占用更多外缘储放空间。 | Patch 002-C | 大仓库 / 深层储藏库 | 已封存原文 | 待判定 | 可作玩家说明，也可作系统口径。 |
| building.warehouse.rule | Building / Storage | 建筑规则提示 | 仓库不占内环、中环、外环普通槽位。仓库只占外缘储放区槽位。 | Patch 002-C | 仓库规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.sheltered_gathering_shed.name | BuildingAttachment / Resource | 附属设施名 | 避寒采集棚 | Patch 002-A / 002-C / 006B-3 | 前期采集点与避寒采集棚 | 已封存原文 | 通用 |  |
| building.sheltered_gathering_shed.desc | BuildingAttachment / Resource | 附属设施说明 | 避寒采集棚本身不是生产建筑，而是资源点安全附件。 | Patch 002-A | 避寒采集棚 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| building.sheltered_gathering_shed.slot_rule | BuildingAttachment / Resource | 附属设施规则 | 避寒采集棚只附属于散落资源点，不占普通槽位。 | Patch 002-C | 避寒采集棚 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
  
   
⸻  
   
## 06_Map / 地图资源点与非建筑资源结构  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------ | -------------- | ----- | ------------------------------------ | -------------------- | ------------- | ------- | ---- | ------------------------------------- |
| map.resource.surface_point.name | Map / Resource | 资源点名 | 地表小型物资点 | Patch 006B-3 | 地表小型物资点 | 已封存原文 | 通用 |  |
| map.resource.surface_point.desc | Map / Resource | 资源点说明 | 地表小型物资点是早期缓冲资源。它们不是长期资源系统。 | Patch 006B-3 | 地表小型物资点 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| map.resource.large_coal_point.name | Map / Resource | 资源点名 | 大型煤矿点 | Patch 002-C / 006B-3 | 地图资源模板 / 大型矿点 | 已封存原文 | 通用 | 资源锚点，本身不占普通槽位。 |
| map.resource.large_steel_point.name | Map / Resource | 资源点名 | 大型钢铁矿点 | Patch 002-C / 006B-3 | 地图资源模板 / 大型矿点 | 已封存原文 | 通用 | 资源锚点，本身不占普通槽位。 |
| map.resource.forest_area.name | Map / Resource | 资源点名 | 森林区 | 用户补充校正；Patch 002-C | 资源点类型 | 用户确认覆盖项 | 通用 | 地图资源锚点；本体不是建筑，不占槽，不直接产木；伐木场绑定森林区建造。 |
| map.resource.hunting_area.name | Map / Resource | 资源点名 | 猎区 | Patch 002-C | 资源点类型 | 已封存原文 | 通用 |  |
| map.resource.scattered_point.name | Map / Resource | 资源点类型 | 普通散落资源点 | Patch 002-C | 资源点类型 | 已封存原文 | 系统内部 | 通用资源点类别；具体 UI 显示名见散落煤炭 / 散落木材 / 散落钢铁。 |
| map.resource.scattered_coal.name | Map / Resource | 资源点名 | 散落煤炭 | 用户补充校正；总控 / 七批补表 | 正式 UI 显示名 | 用户确认覆盖项 | 通用 | 正式 UI 显示名；V1 不设置散落食物点。 |
| map.resource.scattered_wood.name | Map / Resource | 资源点名 | 散落木材 | 用户补充校正；总控 / 七批补表 | 正式 UI 显示名 | 用户确认覆盖项 | 通用 | 正式 UI 显示名；V1 不设置散落食物点。 |
| map.resource.scattered_steel.name | Map / Resource | 资源点名 | 散落钢铁 | 用户补充校正；总控 / 七批补表 | 正式 UI 显示名 | 用户确认覆盖项 | 通用 | 正式 UI 显示名；V1 不设置散落食物点。 |
| map.resource.point_not_building.rule | Map / Resource | 规则提示 | 大型煤矿点、大型钢铁矿点、森林区、猎区、普通散落资源点本身不占普通槽位。 | Patch 002-C；用户补充校正 | 本 Patch 结论 | 用户确认覆盖项 | 系统内部 | 全局重复过多，建议复用。 |
  
   
⸻  
   
## 07_Furnace / 炉心与供暖  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------- | ----------------- | ---- | ---------------------------------- | --------------------------------- | --------------------- | ----- | ---- | --------------------------------- |
| furnace.name | Furnace | 系统名 | 炉心 | Patch 001 / Patch 003 / Patch 004 | 基础定位 / 燃料与炉心消耗 / 炉心命令 | 已封存原文 | 通用 |  |
| furnace.operation.name | Furnace | 状态名 | 炉心运行 | Patch 003 | 燃料用途 | 已封存原文 | 通用 |  |
| furnace.high_power.name | Furnace | 状态名 | 炉心高档运行 | Patch 003 | 燃料用途 | 已封存原文 | 通用 |  |
| furnace.overload.name | Furnace | 状态名 | 炉心过载 | Patch 003 / Patch 004 | 燃料用途 / 过载命令 | 已封存原文 | 通用 |  |
| furnace.shutdown.name | Furnace | 状态名 | 炉心关闭 | Patch 003 / Patch 004 / 006C | 炉心关闭风险 / 面板预警 | 已封存原文 | 通用 |  |
| furnace.fuel_warning.coal_shortage | Furnace / Warning | 预警提示 | 炉心不会自动燃烧木材。系统在 end_day 前给出明确警告。 | Patch 003 | 木材应急燃烧 | 已封存原文 | 待判定 | 若作为 end_day 提示可玩家可见；若仅作规则校验则系统内部。 |
| furnace.fuel_timing.rule | Furnace | 规则提示 | 今日生产煤炭不会回填今日炉心燃料缺口，只用于日结后库存与下一日供暖。 | Patch 003 | 日结顺序 / 全局修正 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| furnace.woodfuel.name | Furnace / Action | 行动名 | 木材应急燃烧 | Patch 003 / Patch 004 | 燃料与炉心消耗 / woodfuel 命令 | 已封存原文 | 通用 |  |
  
   
⸻  
   
## 08_Heat / 应急加热  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------------- | -------------- | ---- | ---------------------------- | ----------------------------------- | ----------------- | ------- | ---- | --------------------- |
| heat.name | Heat | 行动名 | 应急加热 | Patch 002-A / Patch 003 / Patch 004 | 应急加热总原则 / heat 命令 | 已封存原文 | 通用 |  |
| heat.command.format | Heat / Command | 命令格式 | heat <建筑名> | Patch 002-A | 应急加热总原则 | 已封存原文 | 通用 |  |
| heat.rule.start_available | Heat | 规则提示 | heat 开局可用。 | Patch 002-A；总控；006B 修正复核包 | 应急加热装置口径 | 用户确认覆盖项 | 系统内部 | 该名称已由总控覆盖。 |
| heat.rule.device_not_unlock | Heat | 规则提示 | 应急加热装置不是 heat 解锁科技。 | Patch 002-A；总控；006B 修正复核包 | 应急加热装置口径 | 用户确认覆盖项 | 系统内部 | 该名称已由总控覆盖。 |
| heat.rule.device_upgrade | Heat | 规则提示 | 应急加热装置是 heat 强化科技。 | Patch 002-A；总控；006B 修正复核包 | 应急加热装置口径 | 用户确认覆盖项 | 系统内部 | 该名称已由总控覆盖。 |
| heat.rule.auto_off | Heat | 规则提示 | 当日结束后，应急加热自动关闭。 | Patch 003 | 应急加热规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| heat.rule.no_repeat_same_day | Heat | 规则提示 | 同一建筑同日不可重复 heat。 | Patch 002-A | 应急加热总原则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| heat.rule.no_need_no_cost | Heat | 规则提示 | 如果目标建筑温度已经足够，系统提示无需加热，不消耗煤炭。 | Patch 002-A | 应急加热总原则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| heat.rule.house_forbidden | Heat | 规则提示 | 住宅不能靠一键加热解决。 | Patch 002-A | 应急加热装置口径 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| heat.rule.research_lab_default_forbidden | Heat | 规则提示 | 研究所 / 工程研究站当前不列入默认可 heat 建筑。 | Patch 002-A；总控 | 应急加热装置口径 | 用户确认覆盖项 | 系统内部 | 该名称已由总控覆盖。 |
| heat.rule.oath_patrol_forbidden | Heat | 规则提示 | 守炉堂 / 巡查所不需要 heat，也不可 heat。 | Patch 006C-4 | 核心建筑温度口径 | 已封存原文 | 系统内部 | 全局重复过多，建议复用。 |
| heat.rule.hunting_lodge_forbidden | Heat | 规则提示 | 狩猎小屋不允许一键加热。 | Patch 002-A | 狩猎小屋 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| heat.rule.warehouse_forbidden | Heat | 规则提示 | 仓库是容量建筑，不是岗位建筑。 | Patch 002-A | 仓库 | 已封存原文 | 系统内部 | 仅作为 heat 排除提示。 |
  
   
⸻  
   
## 09_RouteBuilding / 守炉堂与巡查所  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------------------ | ---------------- | ----- | ------------------------------------- | ------------------------------ | ------------------ | ------- | ---- | -------------------------- |
| building.oath_hall.name | Building / Route | 建筑名 | 守炉堂 | Patch 006C-1 / 006C-4 | 路线核心建筑 | 已封存原文 | 通用 |  |
| building.oath_hall.desc | Building / Route | 建筑说明 | 守炉堂是誓言路线核心建筑。 | Patch 006C-2 | 核心建筑：守炉堂 | 已封存原文 | 待判定 | 已修正上一版 TODO。 |
| building.oath_hall.core_label | Building / Route | UI 标签 | 核心建筑：守炉堂 | Patch 006C-4 | 006C 面板显示 | 已封存原文 | 通用 |  |
| building.oath_hall.unlock_rule | Building / Route | 解锁提示 | 签署守炉誓言后，守炉堂自动启用，不进入 build 队列。 | 用户补充校正；全局总控 | 核心建筑建造与运行时机 | 用户确认覆盖项 | 待判定 | 全局总控覆盖旧 006C-4 建造权限口径。 |
| building.oath_hall.status_label | Building / Route | UI 标签 | 守炉堂状态：未启用 / 已启用但未值守 / 运行中 | 用户补充校正；全局总控 | 006C 面板显示 | 用户确认覆盖项 | 通用 | 不占槽、不 build；路线入口炉律签署后自动启用。 |
| building.oath_hall.requirement.running | Building / Route | 条件提示 | 守炉堂必须已启用，并处于运行状态。 | 用户补充校正；全局总控 | 终章前置规则 | 用户确认覆盖项 | 待判定 | 终章前置检查读取“启用 + 运行”，不是“建成”。 |
| building.patrol_office.name | Building / Route | 建筑名 | 巡查所 | Patch 006C-1 / 006C-3 / 006C-4 | 路线核心建筑 / 巡查所 | 已封存原文 | 通用 |  |
| building.patrol_office.desc | Building / Route | 建筑说明 | 巡查所是铁腕路线核心建筑。 | Patch 006C-3 | 核心建筑：巡查所 | 已封存原文 | 待判定 | 可作玩家说明，也可作系统口径。 |
| building.patrol_office.core_label | Building / Route | UI 标签 | 核心建筑：巡查所 | Patch 006C-4 | 006C 面板显示 | 已封存原文 | 通用 |  |
| building.patrol_office.unlock_rule | Building / Route | 解锁提示 | 签署炉城巡令后，巡查所自动启用，不进入 build 队列。 | 用户补充校正；全局总控 | 炉城巡令 / 核心建筑建造与运行时机 | 用户确认覆盖项 | 待判定 | 全局总控覆盖旧 006C-4 建造权限口径。 |
| building.patrol_office.status_label | Building / Route | UI 标签 | 巡查所状态：未启用 / 已启用但未值守 / 运行中 | 用户补充校正；全局总控 | 006C 面板显示 | 用户确认覆盖项 | 通用 | 不占槽、不 build；路线入口炉律签署后自动启用。 |
| building.patrol_office.requirement.running | Building / Route | 条件提示 | 巡查所必须已启用，并处于运行状态。 | 用户补充校正；全局总控 | 终章前置规则 | 用户确认覆盖项 | 待判定 | 终章前置检查读取“启用 + 运行”，不是“建成”。 |
| building.route_core.manual_build_rule | Building / Route | 规则提示 | 守炉堂 / 巡查所不需要玩家手动 build；路线入口炉律签署后自动启用。 | 用户补充校正；全局总控 | 核心建筑建造与运行时机 | 用户确认覆盖项 | 系统内部 | 全局总控覆盖旧 006C-4 建造权限口径。 |
| building.route_core.running_rule | Building / Route | 规则提示 | 守炉堂 / 巡查所启用并满足值守后，当日即可运行。 | 用户补充校正；全局总控 | 核心建筑建造与运行时机 | 用户确认覆盖项 | 系统内部 | 守炉堂 / 巡查所不进入 build 队列。 |
| building.route_core.temperature_rule | Building / Route | 规则提示 | 守炉堂 / 巡查所不受低温、黑霜、第七霜落导致的停工影响。 | Patch 006C-4 | 核心建筑温度口径 | 已封存原文 | 系统内部 | 全局重复过多，建议复用。 |
| building.route_core.furnace_off_rule | Building / Route | 规则提示 | 炉心关闭不额外影响守炉堂 / 巡查所。 | Patch 006C-4 | 核心建筑温度口径 | 已封存原文 | 系统内部 | 全局重复过多，建议复用。 |
  
   
⸻  
   
## 10_Facility / 炉旁设施与行动承接物  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------- | ---------------- | ---- | ------------------------ | --------------------- | ----------- | ----- | ---- | ------------ |
| facility.oath_table.name | Facility / Route | 设施名 | 共食台 | Patch 006C-1 / 006C-2 | 炉旁设施 / 誓言路线 | 已封存原文 | 通用 | 已修正上一版误写。 |
| facility.oath_bell.name | Facility / Route | 设施名 | 悼亡钟 | Patch 006C-1 / 006C-2 | 炉旁设施 / 誓言路线 | 已封存原文 | 通用 |  |
| facility.oath_monument.name | Facility / Route | 设施名 | 炉旁誓碑 | Patch 006C-1 / 006C-2 | 炉旁设施 / 誓言路线 | 已封存原文 | 通用 | 已修正上一版误写。 |
| facility.ashes_book.name | Facility / Route | 设施名 | 余烬名册 | Patch 006C-1 / 006C-2 | 炉旁设施 / 誓言路线 | 已封存原文 | 通用 | 已修正上一版误写。 |
| facility.notice_wall.name | Facility / Route | 设施名 | 公告墙 | Patch 006C-3 | 炉旁设施与行动承接物 | 已封存原文 | 通用 |  |
| facility.registry_board.name | Facility / Route | 设施名 | 炉心登记牌 | Patch 006C-1 / 006C-3 | 炉旁设施与行动承接物 | 已封存原文 | 通用 |  |
| facility.guard_post.name | Facility / Route | 设施名 | 执勤岗 | Patch 006C-3 | 炉旁设施与行动承接物 | 已封存原文 | 通用 |  |
| facility.patrol_bell.name | Facility / Route | 设施名 | 巡查铃 | Patch 006C-3 | 炉旁设施与行动承接物 | 已封存原文 | 通用 |  |
| facility.route.not_slot_rule | Facility / Route | 规则提示 | 公告墙、炉心登记牌、执勤岗、巡查铃不是占槽建筑。 | Patch 006C-3 | 炉旁设施与行动承接物 | 已封存原文 | 系统内部 | 全局重复过多，建议复用。 |
  
   
⸻  
   
## 11_Storage / 仓储状态与提示  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ------------------------------- | ------- | ---- | --------------------------------- | --------------------- | ----------------- | ----- | ---- | -------------------------- |
| storage.capacity.name | Storage | 系统名 | 仓储容量 | Patch 003 | 仓储容量 | 已封存原文 | 通用 |  |
| storage.overflow.name | Storage | 状态名 | 爆仓 | Patch 003 | 爆仓规则 | 已封存原文 | 通用 |  |
| storage.temporary_overflow.name | Storage | 状态名 | 临时超仓 | Patch 003 / Patch 004 | 爆仓规则 / end_day 预警 | 已封存原文 | 通用 |  |
| storage.overflow.rule | Storage | 规则提示 | 日常采集和生产无法继续入库。玩家需要消耗资源、建造仓库或升级仓储。 | Patch 003 | 爆仓规则 | 已封存原文 | 待判定 | 若作为爆仓提示可玩家可见；若仅作规则校验则系统内部。 |
| storage.overflow.recover_rule | Storage | 规则提示 | 资源总量降回仓储容量以内后，日常生产恢复。 | Patch 003 | 爆仓规则 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
| storage.no_auto_warehouse.rule | Storage | 规则提示 | 仓储扩容不会自动建造仓库。 | Patch 006B-3 | 仓储扩容 | 已封存原文 | 系统内部 | 代码窗 / 测试窗口径，不直接给玩家显示。 |
  
   
⸻  
   
## 12_TODO_TEXT / 本轮占位  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ---------------------------------------------------- | ------------------ | ------- | --------- | ------------ | ----------- | --------- | --- | ------------------- |
| building.hospital.missing_requirement_hint | Building / Medical | 双前置缺口提示 | TODO_TEXT | Patch 006B-4 | TODO / 命令显示 | TODO_TEXT | 待判定 | 若作为失败提示可玩家可见；正文未封存。 |
| building.greenhouse.upgrade_missing_requirement_hint | Building / Food | 升级缺口提示 | TODO_TEXT | Patch 006B-4 | TODO / 命令显示 | TODO_TEXT | 待判定 | 若作为失败提示可玩家可见；正文未封存。 |
| building.house.upgrade_missing_requirement_hint | Building / Housing | 升级缺口提示 | TODO_TEXT | Patch 006B-4 | TODO / 命令显示 | TODO_TEXT | 待判定 | 若作为失败提示可玩家可见；正文未封存。 |
  
   
⸻  
   
## 13_作废旧口径 / 本轮新增  

| text_id | 模块 | 文案类型 | 中文原文 | 来源文件 | 来源章节 / 位置 | 状态 | 可见性 | 备注 |
| ----------------------------------------------- | ---------- | --------- | --------------------- | -------------------- | ---------------- | ----- | ---- | -------------------------------------------- |
| deprecated.building.workshop | Deprecated | 旧建筑名 | 修造工坊 / 工坊 | Patch 002-A；总控 | 应急加热装置口径 / 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.building.small_underground_coal_iron | Deprecated | 旧建筑名 | 小型地下煤铁开采点 | Patch 002-A / 006B-3 | 并入说明 / 作废旧口径 | 作废旧口径 | 系统内部 | 正式名为“小型采煤机 / 小型采钢机”。 |
| deprecated.resource.other_pickup_remains | Deprecated | 旧资源口径 | 其他可拾取残余资源 | Patch 006B-3 | 地表小型物资点 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.map.resource.lumberyard_point | Deprecated | 旧资源点名 | 伐木场点 | Patch 006B-3；用户补充校正 | 地图资源模板 / 作废旧口径 | 作废旧口径 | 系统内部 | 旧封存表述；正式资源锚点使用 forest_area / 森林区。 |
| deprecated.heat.house_enabled | Deprecated | 旧 heat 口径 | 住宅一键加热 | Patch 002-A | 已删除 / 作废内容清单 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.heat.hunting_lodge_enabled | Deprecated | 旧 heat 口径 | 狩猎小屋一键加热 | Patch 002-A | 已删除 / 作废内容清单 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。 |
| deprecated.route_core.manual_build | Deprecated | 旧路线建筑口径 | 守炉堂 / 巡查所需要玩家手动 build | 用户补充校正；全局总控 | 作废旧口径 | 作废旧口径 | 系统内部 | 作废旧名，仅供排查旧口径回流。最新口径为路线入口签署后自动启用，不占槽、不 build。 |
  
  
