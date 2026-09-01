# PATCH-044：规则查询与终局完整性黑盒修复实现记录

## 1. 来源与范围

Patch 043 合并后的第四十次钢材专项黑盒验收全部通过。第四十一次 seed 44044 完整盲玩在指定 `main` 提交上完成 D55，并复现两项确定缺陷：

1. `{"type":"rules","topic":"final_frost"}` 因缺少正式字段 `section` 而泄漏 `SESSION_REQUEST_FAILED / KeyError`；
2. 终局并不存在 `sedation_city` 标签，但格式 5 仅因签署娱乐炉律就登记 `ending.entertainment.sedation_city.full_text` PENDING，使 24/24 高胜报告错误标为不完整。

同局还提交了未注册的 `game.research_start`。原拒绝只说明命令未注册，必须另行猜测目录查询方式。本 Patch 将其纳入协议发现性修复，但不提供行动推荐或模糊替代命令。

## 2. 规则查询诊断

正式规则查询仍使用：

```json
{"type":"rules","section":"RULE_SECTION_STRING"}
```

缺少 `section`、字段类型错误、误用 `topic`、携带其他多余字段或提交未知栏目时，机器接口返回 `INVALID_RULES_QUERY`，并稳定提供：

- `reason`；
- `field_errors` 或 `submitted_section`；
- `unexpected_fields`；
- 正式 `request_shape`；
- `available_sections`；
- `state_changed=false`。

上述错误不进入游戏命令回放，不改变状态、存档或随机流，也不再落入通用内部异常包络。

## 3. 未注册命令发现性

`COMMAND_NOT_REGISTERED` 继续拒绝未知命令，并新增 `command_discovery`：

- `request_shape={"type":"command_specs"}`；
- 稳定排序的 `registered_command_names`；
- `contains_strategy_recommendations=false`。

接口不猜测玩家想执行的动作，不返回 `suggested_command` 或具体行动参数。机器可以从完整正式目录自行选择协议名称，而不是依赖源代码或错误尝试。

## 4. 终局报告格式 6

`sedation_city` 正式触发公式仍未封存，其正文不进入运行时注册或正文选择。格式 5 的旧合同曾在签署 `tavern_law` 或 `casino_law` 时无条件登记该 PENDING；这会把没有镇静之城事实的合法终局误报为不完整。

新生成报告使用格式 6：

- 只有实际终局标签集合包含 `sedation_city` 时，才登记 `ending.entertainment.sedation_city.full_text`；
- 仅签署酒馆或赌场炉律、建成或运行娱乐设施均不等于触发镇静之城；
- 没有该标签时不加入该 PENDING，报告完整度只由其他真实待定项决定；
- 若未来合法状态实际产生该标签，在正式公式和正文接线完成前仍稳定登记 PENDING，不自行补写正文。

## 5. 兼容与严格校验

存档数据版本保持 v17，不迁移、不重抽已经生成的报告。

- 格式 1～4 沿用各自历史合同；
- 格式 5 通过独立 `patch030` 复算函数严格复载，保留旧 PENDING 集合；
- 旧格式 5 删除既有 PENDING 或伪装成格式 6 会被拒绝；
- 格式 6 无 `sedation_city` 标签却伪造该 PENDING 会被拒绝；
- 尚未生成报告的兼容存档在 D55 正式结算时生成格式 6。

第四十一次黑盒的真实格式 5 终局存档已用本实现成功读取，仍原样显示其历史 `partial_pending_text`，证明修复没有追溯重写旧报告。

## 6. 测试与边界

回归覆盖：

- `topic` 误字段返回缺失 `section`、多余字段、正式形状和合法栏目；
- 未知规则栏目返回稳定原因，随后同会话合法 `final_frost` 查询成功；
- 未注册研究命令返回完整命令目录发现合同，且状态、存档与回放语义不受污染；
- 娱乐炉律存在但无 `sedation_city` 标签时，格式 6 报告完整且可严格往返；
- 伪造格式 6 PENDING 被拒绝；
- 带历史 PENDING 的格式 5 报告继续严格加载。

不修改 JSON、地图、成本、产量、科技效果、炉律、社会路线、终霜门槛、随机流或任何平衡数值；不补写 `sedation_city` 正文，不开始 Patch 045、D56、AI 策略或图形 UI。

完成时实际结果：533 项 unittest 全部通过；9 份 JSON 配置校验、compileall 与 git diff --check 全部通过。
