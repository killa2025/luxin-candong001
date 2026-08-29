# Patch 036：分级救治条件反馈文案接线实现记录

## 1. 范围

本 Patch 只把已经封存的两条分级救治目标条件正文接入正式机器接口：

- 启动分级救治时必须指定一座医疗站或医院；
- 养护所不能作为分级救治目标。

不实现尚未封存的分诊冷却、救治结果、死亡、伤残、信任、恐慌或事件数值；既有合法性顺序、确认协议、存档和随机流均不改变。

Patch 035 已完成复审、合并 `main`，并通过第三十二次纯黑盒专项验收（98 / 98 自动断言、331 条同会话命令结果与回放一致、4 个存档可重开）。

## 2. 权威来源与唯一主键

正文来自：

- `docs/control/《炉心残冬》六轮文案资产表全局总收口  最终终审.md`；
- `docs/control/《炉心残冬》全局修正总控正文【代码窗前置必读】.md`；
- `docs/text-assets/第 3 轮：Route  Law  Mode  Confirm  Requirement  Cooldown.md`；
- `docs/text-assets/第 4 轮：Tech  Research  Medical  Entertainment  Population  Feedback.md`。

文案总收口已指定唯一运行主键：

| text_id | 正文 | 状态 |
| --- | --- | --- |
| `medical.triage.target_rule` | 启动时必须指定一座医疗站或医院。 | `FINAL` |
| `medical.triage.care_home_forbidden` | 不能指定养护所。 | `FINAL` |

`requirement.medical_building.target` 与 `requirement.care_home.not_target` 只是重复交叉索引，不作为独立 runtime 资产注册。

## 3. 机器接口

- `game.triage` 命令规格公开目标条件 `text_id` 与正文模板。
- 正式 `law_view.triage_target_contract` 公开合法建筑类型、养护所禁用状态及两条正文。
- 缺少 `building_id`、`building_id` 类型错误、目标不存在或目标不是医疗站/医院时，拒绝结果附带目标条件正文。
- 若未来存在合法注册的养护所状态，拒绝结果使用养护所专用正文；当前养护所仍是 deferred unlock，本 Patch 不创建该建筑。
- 所有拒绝保持状态、存档和回放事实不污染。

## 4. PENDING 与越界

- `confirm.action.triage.body` 完整高风险确认正文继续为 `TODO_TEXT`，不得把按钮文字误当完整正文。
- `triage_cooldown_days` 及正式分诊结果尚未封存，合法目标仍返回 `triage_balance_not_sealed`，不改变状态。
- 养护所的建造成本、槽位、容量、运行和护理效果不在本 Patch 实现。
- 不修改 `data/`、存档版本、迁移、平衡值、科技、路线、事件或终霜机制。
- 不实现 AI 推荐、图形 UI、D56 或 Patch 037。

## 5. 验证

- 两条正文逐字匹配、状态为 `FINAL`，重复别名未注册；
- 命令规格和正式观察可提前发现目标合同；
- 缺少、类型错误、不存在及非医疗目标均返回结构化条件正文；
- 合法且运行中的医疗目标继续到达既有 `triage_balance_not_sealed` 边界；
- 所有失败状态不变；
- 全量 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均须通过。

完成后停止，不开始 Patch 037。
