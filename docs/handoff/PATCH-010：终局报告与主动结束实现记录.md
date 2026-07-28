# PATCH-010：终局报告与主动结束实现记录

## 完成范围

Patch 010 在既有 D55 终局评分之后完成以下接线：

- D55 正式结算生成可保存的结构化终局报告选择；
- 报告保留原 `ending_state`、六项评分、总分、major / defining 标签、完整 `ending_tags` 与已解锁隐藏成就；
- 正式显示内容只使用已封存、非候选池、可直接证明成立的 `text_id`；
- 无法安全选择的主文案、叙事句、附加句和审问池不进入正文，统一返回稳定、去重、排序的 `pending_text_ids`；
- 新增 `game.end_run`，只允许在 D55 完整结算并生成报告后以 `confirm=true` 主动封存；
- 新增 `furnace-winter report <save.json>` 命令行报告入口；
- 存档版本升级为 v12，并提供 v11 → v12 安全迁移；
- 严格校验报告生成日、原始结局、展示结果、正文 text_id、PENDING text_id、隐藏成就及主动结束历史。

## `game.end_run` 口径

成功执行后：

```text
run_state = ended
termination_reason = player_ended
termination_day = 55
termination_command_sequence = 本次命令序号
```

以下字段保持不变：

- `ending_id`；
- `hard_fail_type`；
- `system_scores`；
- `total_score`；
- `major_tags`；
- `defining_tags`；
- `ending_tags`；
- 人口、资源、信任、恐慌和终霜历史。

命令不会推进日历。首次成功后再次执行返回稳定的 `ILLEGAL_COMMAND / already_ended`，不修改状态或报告。

以下情况拒绝：

- D54 或更早；
- D55 尚未完成正式结算；
- 缺少 `confirm` 或 `confirm` 不是布尔值；
- `confirm=false`；
- 已进入任一硬失败；
- 本局已主动封存。

## 报告文案边界

正式 TextRegistry 只登记：

- 七个终局标题；
- 四个硬失败的一句话原因；
- 玩家主动结束的一句话封存状态与固定收束句。

本轮不把任何 `*.pool` 整体当作正文，也不拆分、不随机抽取、不固定选择第一条。`TODO_TEXT`、PENDING、DEPRECATED 和系统内部条目均不会出现在报告正文。

`ending.report.death_record_sentence` 始终登记为待正式文案。霜落死亡为零时，不显示死亡句或临时替代句，并额外登记：

```text
ending.report.frostfall_deaths.zero_sentence
```

## 存档 v12

`FinalResultState` 新增：

- `run_state`；
- `termination_reason`；
- `termination_day`；
- `termination_command_sequence`；
- `report`。

`report` 保存生成日、原 `ending_state`、展示结果、标题 text_id、固定正文 text_id、PENDING text_id 与隐藏成就 ID。存档不保存候选池随机结果，也不保存临时拼写的正文。

v11 → v12 迁移将运行状态设为 `active`，终止原因与历史为空。未终局存档保持报告未生成；已经具有可验证终局结果的 v11 存档会从既有结果、标签与终霜历史确定性补建结构化报告选择，不补造候选正文或随机历史。

## 测试

完整命令：

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests
python -m furnace_winter validate-config data
python -m compileall -q src tests
git diff --check
```

Patch 010 提交前全量单元测试共 304 项，覆盖：

- D54、D55 未结算、确认参数和硬失败拒绝；
- 主动结束不覆盖原结局、评分和标签；
- 重复执行幂等；
- 零霜落死亡句与死亡记录 TODO 正文完全省略；
- 候选池不随机、不进入正式正文；
- `pending_text_ids` 稳定、去重、排序；
- 报告存档往返、篡改拒绝与 v11 → v12 迁移；
- 命令行读取终局报告；
- D48 → D55 全系统集成后生成报告且不产生 D56。

## 越界自检

本 Patch 未实现：

- 图形、网页或桌面 UI；
- 终局详情数值分页；
- 候选文案浏览器；
- 候选池随机抽取或模糊匹配；
- 009-C 路线专属长文；
- D56、postgame 或 D55 后继续模拟；
- AI 决策、推荐行动或自动策略；
- 任何后续 Patch。

## PENDING

仍以 `docs/PENDING.md` 为唯一跨模块导航，重点保留：

- `ending.report.death_record_sentence`；
- 零霜落死亡的正式替代句；
- 所有终局文案池候选条件元数据；
- 009-C 路线与制度完整结局正文；
- 图形 UI、详情页和 D55 后流程。
