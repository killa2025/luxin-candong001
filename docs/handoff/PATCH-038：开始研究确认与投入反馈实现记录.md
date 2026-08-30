# Patch 038：开始研究确认与投入反馈实现记录

## 1. 范围

本 Patch 只处理 `game.research` 的高风险投入确认缺口。开始研究原本就会立即扣除配置规定的木材、钢材，并建立单一活动研究；本轮不改变该结算，只要求玩家在看到本次研究、实际投入和取消损失事实后显式提交 `confirm=true`。

Patch 037 已完成复审、合并 `main`，并通过第三十四次纯黑盒专项复测。验收使用指定合并提交 `4516a236c7555cfd36114f3dd78de27d09ccf979`；版本门禁修复后，确认取消研究的正文、协议、零返还、进度清零、拒绝原子性和持久化均通过正式入口验证。

## 2. 用户明确确认正文

`research.confirm.body` 使用以下用户明确确认原文：

> 确认开始研究「{technology_name}」？本次研究将立即投入 {wood_cost} 木材与 {steel_cost} 钢材。研究完成前，这些资源不会返还；若中途取消，已经投入的资源与研究进度都将损失。

该正文登记为 `USER_OVERRIDE`、`PLAYER_VISIBLE`。`technology_name`、`wood_cost` 与 `steel_cost` 只能来自本次 `tech_id` 对应的已验证科技配置，不接受调用方自填正文或成本。

本口径取代 Patch 034 的旧兼容口径。Patch 034 当时将同一 `text_id` 作为非确认性质的执行前说明，并明确不为 `game.research` 增加 `confirm`；用户在 Patch 038 重新确认了“确认开始研究”正文，因此从本 Patch 起正式命令必须显式确认。

## 3. 命令合同

- `game.research` 保留必填字符串参数 `tech_id`，新增可选布尔参数 `confirm`；它不是预览开关，只接受 `true` 作为执行确认。
- 科技不存在、研究队列被占用、科技已完成、前置或层级未解锁、正式工程师研究所缺失、资源不足等既有拒绝继续优先返回，不被确认门槛遮蔽。
- 研究本身合法但缺少 `confirm` 时返回 `confirmation_required`，状态不变。
- 显式提交 `confirm=false` 时沿用统一的 `confirm_false_is_not_preview` 拒绝，不开始研究。
- `confirm=true` 时保持既有正式结果：立即扣除配置中的木材与钢材，研究进度从 0 开始，所需进度仍按既有研究天数和每日进度单位计算。

命令规格和科技规则查看接口提前公开正文模板、参数来源、`confirm=true` 语义、支付时点、取消零返还与取消不保留进度。确认拒绝同时返回：

- `technology_id` 与 `technology_name`；
- `resource_cost`；
- `research_days` 与 `research_required_units`；
- `payment_timing=on_start`；
- `cancellation_refund`，固定为木材 0、钢材 0；
- `cancellation_progress_retained=false`。

这些字段只说明本次研究投入和既有取消后果，不包含是否应研究该科技的推荐。

## 4. 事务、存档与兼容

- 缺省确认和 `confirm=false` 均不增加 `state_sequence`、不写主存档、不扣资源、不建立研究队列，也不改变随机状态；作为真实命令尝试，它们仍按既有协议各占一条会话级回放记录。
- 成功开始研究继续通过 `GameSession` 的既有原子保存路径提交；保存失败时沿用统一事务回滚。
- 不新增状态字段，不提升存档版本，也不迁移旧存档。既有 v17 存档的活动研究保持原样；只对本 Patch 后新提交的开始研究命令应用确认协议。
- 科技成本、研究天数、研究速度和科技效果仍从相同的已验证运行配置读取；本 Patch 不修改任何 JSON 配置。

## 5. PENDING 与越界

- `confirm.action.triage.body` 仍为 `TODO_TEXT`；正式分诊结果与冷却尚未封存。
- 不修改研究成本、研究天数、研究速度、科技效果、取消研究结果、资源产出、地图、炉律、事件、终霜、评分或平衡值。
- 不实现 AI 推荐、自动策略、图形 UI、D56 或 Patch 039。

## 6. 验证范围

- 用户确认正文逐字匹配，状态为 `USER_OVERRIDE`；
- 命令规格公开可选 `confirm`、确认语义、正文模板及三个参数来源；
- 既有非法条件与资源不足继续优先返回；
- 合法研究缺省确认返回动态科技名称、成本、研究进度需求、支付时点和取消损失事实；
- `confirm=false` 专用拒绝、`confirm=true` 成功扣费并建立研究；
- 两类确认拒绝状态、主存档与 `state_sequence` 不变，回放只记录事实尝试；
- 成功开始研究持久化后可严格重载；
- 全量 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均须通过。

完成后停止，不开始 Patch 039。
