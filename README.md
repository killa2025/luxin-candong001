# 炉心残冬

《炉心残冬》项目仓库。

代码 Patch 026～046 及各自复审修正均已并入 `main`。Patch 047 修复新日结的基础煤统计，并补齐评分限制解释、协议与行动条件发现性、D49 选项文字；不改变平衡数值。历史测试结果保留在实现记录中，不在玩家入口提供旧局经验。新建局使用 `patch045` 平衡档，正式机器标准流为 UTF-8；旧记录和已生成报告不在加载时自动改分或重抽文案。

游戏的实际玩家是运行在沙盒中的 AI，人类用户负责旁观。这个产品定位不产生 AI 专属规则：游戏仍通过通用结构化命令和状态接口运行，不提供决策评分、推荐行动或自动策略。

## 目录概览

Patch 030、Patch 031、Patch 032、Patch 033、Patch 034、Patch 035、Patch 036、Patch 037、Patch 038、Patch 039、Patch 040、Patch 041、Patch 042、Patch 043、Patch 044、Patch 045 与 Patch 046 的既有合同继续有效。

- `docs/`：项目文档
- `data/`：数据文件
- `src/`：源文件
- `tests/`：测试文件

上传内容前请阅读 [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md) 与 [docs/INDEX.md](docs/INDEX.md)。

## 技术方案

- Python 3.12；正式运行代码只使用标准库。
- pytest 是可选开发依赖，不是生产依赖。
- 游戏逻辑、数据配置和未来 UI 分离。
- 数值与玩家文案后续分别从 `data/` 配置和 `text_id` 注册系统读取。
- JSON 运行配置使用 UTF-8，兼容有无 BOM；顶层必须是对象并声明合法的运行态 `config_status`。
- 所有未来随机性必须使用统一的 `DeterministicRandom`；随机种子及生成器状态可以保存和恢复。
- 相同初始状态、相同随机种子和相同行动序列必须得到相同结果。
- `game.end_day` 与 `game.confirm_end_day` 执行固定阶段日结；Patch 007 在推进到新一天后先结算承诺，再按 1 重大 + 1 普通或 2 普通的上限生成事件；Patch 019 将当日兑现的承诺另记为 `events.promise.settled` 结构化日志。
- `game.resolve_old_city_event` 处理旧城派固定阶段事件；未处理的旧城派阶段事件会硬阻断日结。`old_city_view` 同时返回活动阶段的正式标题、正文、选项文字与结构化预览。
- `game.sign_oath_order_law`、`game.staff_oath_order_facility` 与 `game.use_oath_order_action` 分别处理 006C 签署、守炉堂/巡查所派驻及路线主动行动；两条路线永久互斥，特殊设施自动启用、零槽位且不通过 `build` 建造。
- `game.resolve_event` 处理当前可执行事件选项；重大事件未处理时硬阻塞日结，普通事件允许忽略且不会在后台偷偷结算。
- `game.end_run` 只允许在 D55 完整结算、评分和报告已经生成后以 `confirm=true` 主动封存本局；它保留原 `ending_id`、评分和标签，只另记 `run_state=ended` 与 `termination_reason=player_ended`。
- 终局报告保存实际选中的 `text_id` 和报告格式版本；Patch 020 使用本局种子对符合状态的封存候选文案作稳定选择，Patch 021 再用同日服务快照证明医疗与食堂经历。Patch 027 的格式 3 报告以 D55 服务事实和终局实际库存过滤主报告句，Patch 029 的格式 4 报告为这些事实分支接入用户确认正文，Patch 030 的格式 5 再按已签炉律、已建/运行设施、旧城结算与承诺事实接入路线和制度长文。Patch 044 的格式 6 修正 `sedation_city` PENDING 适用条件；格式 1～5 均按各自合同原样严格读取，不在加载时重抽，也不能用其他格式形状绕过校验。
- `GameSession` 是供沙盒 AI 使用的统一运行入口：新建或读取存档后，同一对象登记 27 个现有游戏命令，其中 26 个属于当前可执行能力，`game.triage` 作为暂停能力保留；成功修改状态的命令会原子保存，保存失败则回滚本次命令。
- `GameSession.status()` 每次只返回当前生存与规划所需的紧凑事实；`observe()` 返回完整机器观察，分别列出 `available_commands` 与 `unavailable_commands`，并提供全部 `available_rule_sections`、正式 `play_envelopes`、规则查询协议、持久化文件角色、日结确认生命周期和序列语义；`command_specs` 查询保留全部命令及其 `command_exists`、`executable`、`unavailable_reason`。`rules_view(section)` 按模块返回已验证的原始配置及其 `FINAL` / `TEST_NUMERIC` 状态，不提供策略建议。炉律规则另公开 `overtime_target_contract`，列出允许类型、当前实例资格和阻塞原因；路线行动参数明确指向 `oath_order.action_rules` 中的逐项前置条件。命令规格通过 `related_rule_sections` 指向建筑、科技、炉律、事件、路线、生存与终局规则来源，并通过 `related_protocol_contracts` 指向日结确认等非游戏规则协议，不必先提交失败命令才能发现合法结构。
- `GameSession.replay_document()` 与 `write_replay()` 导出本次进程从打开存档开始的确定性命令记录；它不伪装成此前整局历史。`replay_sequence` 只编号当前会话中实际记录的命令尝试，包含拒绝命令并在重开会话时重置；`state_sequence` 保存于游戏状态，只在状态成功提交时递增，并由请求字段 `expected_state_sequence` 用于并发校验。
- `game.set_furnace` 在白天设置最终炉心档位 `0～3`；炉心关闭或燃料不足会在 `end_day` 前产生结构化强警告。若日结实际有效炉级为 0，当日至少发生 1 例自然死亡；疾病、饥饿优先结算，只有两者均未造成死亡时，既有寒冷系统才保证至少 1 人冻死。警告会分别返回无条件的自然死亡下限与有条件的寒冷死亡下限，不预先断言具体死因。
- `data/survival.json` 保存已封存的开局值、炉心档位、食物基础规则、固定天气与区域修正。
- `data/buildings.json` 保存建筑、地表资源点、升级、区域槽位、`heat` 和测试态 `woodfuel` 数值；其中 `TEST_NUMERIC` 项必须经测试窗复核后才能视为最终平衡值。
- `data/maps.json` 保存三张 V1 地图、共享小型资源点/猎区/森林数量、33/34/33 随机权重与大型煤钢矿点差异；地图差异不修改天气、人口、开局资源或其他生存规则。
- `data/laws.json` 保存 006A 炉律关系、配给、工时、医疗与社会行动规则，包括已登记为 `TEST_NUMERIC` 的过劳患病公式、事故风险点、Patch 013 额外医疗配给 5 食物/人、最多 10 人、冷却 5 天，以及 Patch 019 火盆集会每日被动恐慌下限 20；未封存的分诊结果及事故结果不进入运行配置。Patch 040 暂停分诊命令，Patch 041 同步暂停会解锁该动作的 `triage_law`，均不补造任何数值。
- `data/technologies.json` 保存 37 项 006B 科技、单队列研究规则、第二研究所精确倍率与过载压力规则；Patch 039 为每项科技提供稳定说明，普通 `DEFERRED` 项禁止新开研究且不伪造运行效果，炉心功率稳定 I 仅作为可研究的结构前置保留。科技视图同时公开钢材与木材供应链中已经不可逆的资源缺口；Patch 042 的木材判断使用 D49 前的保守可采上界，Patch 043 的钢材判断继续使用当前派员口径但完整计入尚未支付的钢材筛选与首座小型采钢机成本。
- `data/events.json` 保存 Patch 007 事件阈值、承诺期限与奖惩、固定增员预设和第七霜落预警日；这些试玩数值保持 `TEST_NUMERIC`。
- `data/oath_order.json` 保存代码 Patch 008 的旧城派阈值、006C 解锁、炉律关系、行动成本与冷却；Patch 019 只继续覆盖誓言路线的暂行测试值，铁腕值保持不变，全部继续标记为 `TEST_NUMERIC`。
- `data/final_frost.json` 保存代码 Patch 009 的终霜规则、Patch 013 的寒冷/饥饿/木材断链、Patch 022 的准备与终局分档测试阈值，以及 Patch 045 的新局高胜与完美社会门槛；这些平衡数值保持 `TEST_NUMERIC`。
- 当前存档数据版本为 v18。新建局使用 `patch045` 档；同等级、同住房状态的人口会先汇总再计算寒冷患病，高胜最低总分为 24，社会系统 4 分要求信任至少 85、恐慌至多 15。v17 → v18 只升级结构版本并保留旧局已有的 `legacy_patch021` 或 `patch022` 档，因此旧局继续使用历史患病取整和评分门槛。尚未生成终局报告的兼容存档会在正式终局时生成当前格式 6 报告；已经生成的格式 1～5 报告保持原样并按各自合同严格复载。v16 → v17、v15 → v16、v14 → v15 及此前迁移语义保持不变。

## 开发命令

无需安装第三方依赖即可运行统一测试。在 Windows PowerShell 中：

```text
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

在 macOS 或 Linux 中：

```text
PYTHONPATH=src python -m unittest discover -s tests -v
```

安装可选测试依赖和项目入口：

```text
python -m pip install -e ".[test]"
python -m pytest
python -m furnace_winter validate-config data
python -m furnace_winter state --seed 2025
python -m furnace_winter report path/to/save.json
python -m furnace_winter play path/to/save.json --data-dir data --seed 2025
```

Python 沙盒也可直接使用：

```python
from furnace_winter import GameSession

game = GameSession.open(
    "furnace_winter_save.json",
    config_dir="data",
    seed=2025,
    map_mode="random",
)
print(game.status())
print(game.command("game.set_furnace", {"level": 2}))
print(game.command("game.end_day"))
```

Patch 044 的机器诊断边界：规则查询缺少 `section`、误用 `topic` 或提交未知栏目时会返回请求形状、合法栏目和字段错误，不泄漏内部异常。未注册命令返回 `command_specs` 请求形状及完整注册命令名清单；两类诊断均不做模糊行动推荐。

Patch 045 的机器与平衡边界：`observe()` 的终霜视图公开当前平衡档、五档总分门槛、社会系统 4 分条件及寒冷患病分组口径。命令行启动时会把标准输入、标准输出和标准错误流固定为 UTF-8，避免 Windows 本地代码页损坏中文 JSON；这不改变 JSON 协议、随机流或游戏状态。

Patch 046 的机器发现边界：`game.overtime` 的允许建筑类型、当前目标实例、派员、预计运行状态、资格与阻塞原因可从 `observe().law_view` 或 `rules(laws).interface_text` 直接读取；目标拒绝也返回同一合同。该清单只陈述当前合法性，不推荐选择。`game.use_oath_order_action` 的参数语义明确指向既有路线逐项规则，其中悼亡钟的累计死亡条件早已存在，本轮未修改条件或收益。

Patch 047 的反馈边界：初始观察的 `protocol_contract.play_envelopes.command_request_contract` 直接列出命令形状、字段与默认值，完整命令目录由 `{"type":"command_specs"}` 查询。结构化命令使用 `name`，不是 `command` 别名；纯协议形状如下（大写字符串为占位符，不是可执行动作）：

```json
{"name":"COMMAND_NAME_STRING","arguments":{}}
```

也可包为 `{"type":"command","request":{"name":"COMMAND_NAME_STRING","arguments":{}}}`。`command_id` 和 `expected_state_sequence` 可省略，由会话按公开默认值补齐。派员人数为绝对目标，最小 1；撤员人数若填写也至少 1，省略则清空对应岗位。普通追思的累计死亡、墓园、炉律、冷却与规划日要求公开于 `rules(laws).interface_text.action_rules.memorial`。

建筑状态的 `can_heat` 只表示该类型支持加热，不代表当前可以执行。初始/完整观察的 `heat_view` 与 `rules(buildings).interface_text.heat_target_contract` 返回同一当前资格合同：预计未加热温度必须严格低于运行门槛，每座每天一次、全城次数未用尽，且扣除供暖煤预留后须够支付加热费用。预留公式为 `max(预计有效炉级基础煤耗 - 可用木柴替代量, 0) + 目标过载煤耗`，`reserve_components` 逐项公开组成；这是当前预留计算，不代表已经付款或已经消耗木柴。每个目标给出 `eligible_now` 与按实际校验顺序返回的首个阻塞原因；等于温度门槛也不得加热。查询只陈述条件，不推荐行动、不改变资源或已存状态。

终霜“缺煤日”只统计基础供暖煤耗未完整支付，不混入过载费用，木柴也不作为煤炭储备评分。`final_frost_view.scoring_contract.result_caps` 公开所有既有分档上限；正式 `{"type":"rules","section":"final_frost"}` 查询在 `rules.interface_text.scoring_contract` 返回同一合同，原始配置仍在 `rules.document`，不被覆盖。`final_frost_view.final_result.score_explanation` 和会话 `ending_report_view.score_explanation` 解释已保存分数与实际记录结局。报告中的旧 `limiting_factor_ids` 不是完整降档清单，新解释不改写它，也不重算旧每日记录或旧报告。D49 唯一确认选项显示用户确认的“守住炉城。”，效果不变。

`play` 使用一行一个 JSON 对象的长连接协议。新局默认使用 `--map-mode random`；自选时使用 `--map-mode manual --map-key rustbone_tundra|black_ash_lowland|twin_source_rift`。直接发送结构化命令即可；另支持 `{"type":"observe"}`、`{"type":"status"}`、`{"type":"command_specs"}`、`{"type":"rules","section":"maps"}`、`{"type":"autosave"}`、`{"type":"replay"}` 与 `{"type":"quit"}`。未知包络会返回全部合法类型，不提供行动建议。完整规则栏目由观察结果的 `available_rule_sections` 提供；`rules.query` 不是游戏命令，若误作命令提交，拒绝结果会返回上述正式请求形状。强警告日结返回的确认令牌只在产生预览的同一个存活 `GameSession` 中有效，重连后必须重新预览。成功日结的 `warnings` 同时保留 `pre_settlement` 风险快照和 `settlement_result` 事实；后者明确返回本次实际死亡、遗体处理、结算后仍未处理遗体，以及当日耗尽资源点与自动释放岗位，不代表新增规则或预测。成功日结会在主存档之外写入同目录的 `<存档名>.autosave_end_day.json`，其中保留当日日结清理完成、日期推进前的锁定状态、日志与 `resume_stage`；它不会覆盖或替代主会话存档，也不能直接作为 `play` / `report` 的主存档。打开主存档后使用 `{"type":"autosave"}` 可严格读取最近快照；损坏快照返回 `AUTOSAVE_SNAPSHOT_INVALID` 及稳定的路径、字段、原因和约束，恢复阶段错误另列正式合法值。误把快照路径用于正式入口时返回 `AUTOSAVE_SNAPSHOT_NOT_PRIMARY_SAVE` 和只读查看方式，只有唯一可识别的主存档候选才给出单一路径，无扩展名与 `.json` 候选同时有效时会明确报告歧义。建立新局时主存档与自动保存作为同一个持久化集合检查：默认拒绝任何旧文件，显式覆盖会事务式写入新主存档并清除上一局自动保存。回放导出默认拒绝覆盖已有文件；显式覆盖前会严格解析全部回放条目，并始终禁止指向主存档、自动保存或运行配置。具体边界见 `docs/handoff/PATCH-011：统一游戏会话与沙盒入口实现记录.md`、`docs/handoff/PATCH-012：三地图开局与确定性随机实现记录.md` 与 `docs/handoff/PATCH-028：自动存档快照与机器恢复说明实现记录.md`。
