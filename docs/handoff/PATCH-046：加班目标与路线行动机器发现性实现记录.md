# Patch 046：加班目标与路线行动机器发现性实现记录

## 来源与结论

- 来源：Patch 045 合并后的第四十四次 seed 45145 锈骨冻原唯一纯黑盒盲玩。
- 确定缺陷：`game.overtime` 只声明任意 `building_id`，正式规则和拒绝结果都没有列出允许类型或当前合法实例，盲玩者只能枚举失败。
- 黑盒误判：报告称悼亡钟没有公开死亡前置条件；实际 `observe().oath_order_view.action_rules` 与 `rules(oath_order).interface_text.action_rules` 已公开 `requires_recorded_death` 和当前是否满足。Patch 046 不改变该机制，只让命令参数语义直接指向逐项规则。

## 实现范围

1. `game.overtime` 的命令规格说明 `building_id` 受 `overtime_target_contract` 约束。
2. 炉律机器视图与正式 `laws` 规则查询返回同一合同：固定排序的允许建筑类型、已签炉律、每日次数、派员、预计运行及确认要求，以及每座现有建筑的当前资格与阻塞原因。
3. 未知建筑、类型不允许、无人派驻或预计停工的拒绝结果返回同一合同，失败不改变状态。
4. `game.use_oath_order_action.action_id` 的参数语义明确指向 `oath_order.action_rules`，避免把候选枚举误解为全部即时可执行。

## 边界

- 不修改允许加班的建筑类型、加班收益、代价、炉律、路线行动、死亡条件或任何平衡配置。
- 不新增推荐、评分、自动选择或行动排序。
- 不升级存档版本，不改变随机流、D55、终局报告或既有回放语义。

## 验证

- 专项测试覆盖允许类型、当前合法实例、阻塞原因、拒绝回传、正式规则查询和路线参数导航。
- 全量 541 项 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均通过。
