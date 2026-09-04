# Patch 047：加热条件发现性补充记录

## 来源与范围

第四十七次燃料不足边界补测已通过：D53 基础需/付 120/120、目标过载需/付 55/0，不记基础缺煤；D54 基础需/付 120/35、有效炉级 1，仍有 18 煤但基础缺煤为真。203 项证据哈希复算一致。专项另发现 `game.heat` 被 `temperature_already_sufficient` 拒绝前，正式规格和建筑规则未明确公开温度前置；`can_heat=true` 被误解为当次可执行资格。

用户要求继续处理。本修复不分配 Patch 048，不新增规则、文案剧情或数值，仅公开原有加热合法性。

## 接口合同

- `Observation.heat_view` 为仅关键字新增字段，保留全部旧位置参数接口；正式会话初始/完整观察及 CLI state 均接入。
- `rules(buildings).interface_text.heat_target_contract` 返回同一合同；配置 `document` 与 `config_status` 不变。
- `game.heat.building_id` 的参数语义指向该目标合同。
- `can_heat` 仅是建筑类型能力，不是充分的当前执行条件。合同公开支持的类型、严格温度比较、每建筑/全城日次数限制、加热煤耗及预计有效炉级的基础煤预留。
- 所有目标按 building_id 排序，公开预计未加热温度、运行门槛、`eligible_now`、拒绝码、首个阻塞原因与详细事实。资格直接调用现有 `_legality`，不复制另一套判定；现有规划日、失败/终局、类型、当天加热、全城限额、温度及煤储备的优先级不改。
- 合同对当前合法状态及格式正确的目标请求负责；不承诺畸形协议、陈旧状态序列或磁盘故障一定执行成功，不给出策略或行动推荐。

## 验证与边界

新增 5 项测试：温度低于/等于/高于门槛；真实暖日、煤预留不足和锁定日；成功加热后建筑/全城限额及不支持类型；查询/拒绝/严格复载的状态与存档只读性；正式 JSON 行观察与规则查询同源。旧报告、存档版本、配置、加热效果和校验顺序不变。

全量命令（先设置 `PYTHONPATH=src`）：

- `python -m unittest discover -s tests -q`：557 项通过。
- `python -m furnace_winter validate-config data`：9 份 JSON 通过。
- `python -m compileall -q src tests`：通过。
- `git diff --check`：通过。

不进入 Patch 048、D56，不调整平衡。本小修仍需独立审核和 heat 发现性黑盒，不能用之前煤务 PASS 代替。
