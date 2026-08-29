# Patch 037：取消研究确认与损失反馈实现记录

## 1. 范围

本 Patch 只处理 `game.cancel_research` 的高风险确认缺口。取消研究原本就会清空当前进度且不返还已经支付的木材、钢材；本轮不改变该结算，只要求玩家在看到当前研究损失事实后显式提交 `confirm=true`。

Patch 036 已完成复审修正、合并 `main`，并通过第三十三次纯黑盒专项验收。验收使用指定合并提交 `afc1812530f1e73ac62a5b70fe24ffcfce3c36f5`，169 个证据文件确认分级救治目标规则可发现、拒绝原子、畸形协议稳定且没有越界执行分诊数值。

## 2. 用户明确确认正文

`research.cancel.confirm` 使用以下用户明确确认原文：

> 确认取消正在进行的「{technology_name}」研究？已经投入的木材与钢材不会返还，当前研究进度也会清零。

该正文登记为 `USER_OVERRIDE`、`PLAYER_VISIBLE`。`technology_name` 只能来自当前活动研究对应的已验证科技配置，不接受调用方自填正文。

## 3. 命令合同

- `game.cancel_research` 新增可选布尔参数 `confirm`；它不是预览开关，只接受 `true` 作为执行确认。
- 存在活动研究但缺少 `confirm` 时返回 `confirmation_required`，状态不变。
- 显式提交 `confirm=false` 时沿用统一的 `confirm_false_is_not_preview` 拒绝，不执行取消。
- 不存在活动研究时，普通缺省请求继续返回 `no_active_research`；不得伪造待取消对象。
- `confirm=true` 时保持既有正式结果：活动研究清空，当前进度和所需进度归零，木材与钢材返还均为 0。

命令规格提前公开正文模板及动态研究名称的字段来源。确认拒绝同时返回：

- `active_research_id`；
- `active_research_name`；
- `paid_resources`；
- `research_progress_units`；
- `research_required_units`；
- `refund`，固定为木材 0、钢材 0。

这些字段是当前取消对象的事实说明，不包含继续或取消研究的推荐。

## 4. 事务、存档与兼容

- 缺省确认和 `confirm=false` 均不增加 `state_sequence`、不写主存档、不改变资源、研究队列或随机状态；作为真实命令尝试，它们仍按既有协议各占一条会话级回放记录。
- 成功取消仍通过 `GameSession` 的既有原子保存路径提交；保存失败时沿用统一事务回滚。
- 不新增状态字段，不提升存档版本，也不迁移旧存档。既有 v17 进行中研究在加载后保留原队列，下一次取消必须使用新确认协议。
- 科技成本仍从同一份已验证运行配置读取；本 Patch 不修改任何 JSON 配置。

## 5. PENDING 与越界

- `confirm.action.triage.body` 仍为 `TODO_TEXT`；正式分诊结果与冷却尚未封存，不能借取消研究确认补丁接入。
- 额外医疗配给的动态确认正文不在本 Patch 范围。
- 不修改研究成本、研究天数、研究速度、科技效果、资源产出、地图、炉律、事件、终霜、评分或平衡值。
- 不实现 AI 推荐、自动策略、图形 UI、D56 或 Patch 038。

## 6. 验证范围

- 用户确认正文逐字匹配，状态为 `USER_OVERRIDE`；
- 命令规格公开可选 `confirm`、确认语义、正文模板及参数来源；
- 缺省确认返回动态名称、支付资源、当前/所需进度与零返还事实；
- `confirm=false` 专用拒绝、`confirm=true` 成功取消；
- 两类拒绝状态、主存档与 `state_sequence` 不变，回放只记录事实尝试；
- 成功取消持久化后可严格重载；
- 全量 495 项 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均通过。
