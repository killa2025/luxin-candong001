# Patch 039：科技说明与延后研究门禁实现记录

## 1. 范围

本 Patch 为 37 项现有科技登记稳定的玩家说明 `text_id`，把说明接入科技机器视图和科技规则查询，并收紧 `DEFERRED` 科技的新研究入口。科技成本、研究天数、研究速度、已实现效果和科技树关系保持不变；不新增任何尚未封存的运行机制。

科技说明统一使用：

`tech.<config tech_id 去掉 tech_ 前缀>.desc`

例如 `tech_overload_tuning` 对应 `tech.overload_tuning.desc`。`tech.xxx.desc` 只是旧资料中的主键形状示意，不是可注册的字面主键。

说明正文先写可验证的效果事实，再保留少量氛围；成本和研究天数继续只从 `data/technologies.json` 的当前配置读取，不复制进静态说明。

## 2. DEFERRED 研究门禁

普通 `DEFERRED` 科技不得新开研究。玩家反馈固定为：

> 该研究目前尚无法投入实际应用。

机器视图同时返回 `status=unavailable`、`effect_status=DEFERRED`、`technology_class=unavailable_application`、`new_research_allowed=false` 和稳定拒绝原因 `technology_not_available_for_application`。这不会把开发术语放入玩家正文。

当前受门禁约束的科技为：

- 散落采集工具；
- 避寒采集棚改良；
- 深井矿架；
- 深层煤脉开采；
- 深层钢脉开采；
- 狩猎装备；
- 外勤防寒装备。

`tech_field_cold_weather_equipment` 的封存目标 `outdoor_exposure_risk` 保留，但在统一外勤暴露系统建立前不提供效果，也不得新开研究；因此其运行元数据由 `ACTIVE/passive` 纠正为 `DEFERRED/deferred`。

## 3. 唯一结构前置例外

`tech_furnace_power_stability_1` 继续保留 `DEFERRED` 元数据，但它是唯一允许新开研究的结构前置。若封锁该项，过载调校、过载稳定和终极炉心稳定链会不可达。

玩家说明使用用户确认正文：

> 建立炉心高功率运行的稳定基础，并开放后续过载调校研究；本身不提供独立运行加成。

机器视图将其标记为 `technology_class=structural_prerequisite`、`new_research_allowed=true`。它只满足既有科技前置关系，不改变炉心煤耗、建筑保温、heat、过载压力或其他独立运行数值。

## 4. 兼容与事务

- 既有存档中已经完成的 `DEFERRED` 科技原样保留，不删除、不退款、不改写历史。
- 既有存档中正在研究的 `DEFERRED` 科技可以继续推进并完成；门禁只作用于未来的新研究开始请求。
- 被拒绝的新研究不扣资源、不建立队列、不增加 `state_sequence`、不写主存档；会话回放只记录这一事实拒绝。
- 不新增状态字段，不提升存档版本，不重抽随机状态。

## 5. 机器查询

每项科技的正式观察增加：

- `description_text_id`、`description_text`、`description_status`；
- `effect_kind`、`effect_targets`、`effect_status`；
- `technology_class`、`new_research_allowed`、`unavailable_reason`。

`rules_view("technologies")` 的 `interface_text.descriptions` 提供完整、稳定排序的 37 项说明目录。该目录只呈现事实和可用性，不提供研究推荐、决策评分或自动策略。

## 6. PENDING 与越界

- 普通 `DEFERRED` 科技的正式效果、产出、风险、建筑和统一外勤暴露系统仍待封存；本 Patch 不反推实现。
- 科技成本、研究天数和第二研究所倍率继续保持现有 `TEST_NUMERIC` 状态。
- 不修改生产、资源、建筑、地图、炉律、事件、终霜、评分或社会路线平衡。
- 不实现图形 UI、AI 策略、D56 或 Patch 040。

## 7. 验证范围

- 37 项科技说明一项一主键、无字面 `tech.xxx.desc`；
- 唯一结构前置可研究、可完成并使后续过载调校达到可确认状态；
- 结构前置本身不产生独立运行加成；
- 其余 7 项普通 `DEFERRED` 科技新开研究均被原子拒绝；
- 已完成和进行中的旧 `DEFERRED` 状态可严格复载，进行中研究可继续完成；
- 规则查询、主存档与会话回放中的科技状态和拒绝原因一致；
- 全量 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均须通过。

施工完成时实际结果：506 项 unittest 全部通过；9 份 JSON 配置校验、`compileall` 与 `git diff --check` 全部通过。
