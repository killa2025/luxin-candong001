# Patch 021：终霜逐日服务事实与终局文案接线实现记录

## 完成范围

Patch 021 只补足 Patch 020 因历史事实不可证明而暂停的三条终局附加句，不修改游戏数值或生存机制。

- D49～D55 的 `FrostDayRecord` 每日保存 `service_history_known`、`canteen_operational`、`medical_operational_building_count` 与 `medical_building_capacity`。
- `FinalFrostSystem.observe()` 以日期排序返回 `daily_service_history`，存档和回放中的同一状态保持一致。
- `ending.additional.food.01` 仅在第七霜落七天中至少一天食堂实际运行时进入候选；不要求七天全程运行。
- `ending.additional.medical.01` 仅在同一已知日同时存在实际运行医疗建筑、正医疗容量、疾病死亡，且该日医疗没有崩溃或医院停摆时进入候选。
- `ending.additional.medical.02` 仅在同一已知日同时存在实际运行医疗建筑、正医疗容量、疾病死亡和医疗溢出时进入候选。
- `ending.additional.medical.03` 继续沿用 Patch 020 的同一座终局运行医疗建筑中同时存在正式医生与医疗学徒条件。

## 存档迁移与严格校验

当前存档数据版本升级为 v16。

- v15 → v16 不从终局建筑倒推过去；既有每日记录统一迁移为 `service_history_known=false`，其余服务事实为零值。
- 迁移后的旧局若无法证明适用条件，对应 `text_id` 继续进入稳定、去重、排序的 `pending_text_ids`，不会展示正文或重抽报告。
- 旧档继续游玩后，新产生日期写入已知事实；未知记录只能形成连续前缀，禁止已知日之后再次出现未知日。
- 未知历史不得携带食堂运行、医疗建筑数或医疗容量；医疗建筑数与容量必须同时为零或同时为正，容量不得小于运行建筑数。
- 伪装成 v15 及更早版本的文档不得提前携带非默认 Patch 021 事实。

## 文案与 PENDING

三条封存正文重新进入运行时 `TextRegistry`。`PendingRegistry` 仍保留相同稳定 ID，用于表达旧档历史不可证明，而不是表示正文未封存。

以下项目仍未实现：

- `ending.trace.children_protected` 的互斥学徒路线适配正文；
- 009-C 完整路线长文；
- 候选池正式随机权重；
- 图形终局页、D56、AI 决策或推荐；
- 任何平衡数值调整。

## 验证

- 全量 `unittest`：418 项通过。
- 9 份 JSON 配置：全部通过 `validate-config`。
- `compileall`：通过。
- `git diff --check`：通过。

## 越界自检

- 未修改 `data/` 下任何平衡配置。
- 未增加新命令、AI 策略、推荐行动、UI 或 D56。
- 未从旧档终局建筑推断历史服务。
- 未开始 Patch 022。
