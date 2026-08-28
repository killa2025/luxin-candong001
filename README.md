# 炉心残冬

《炉心残冬》项目仓库。

代码 Patch 026～033 及各自复审修正均已并入 `main`；Patch 030、Patch 032、Patch 033 已分别通过第二十八次、第二十九次、第三十次纯黑盒验收，Patch 031 已完成事件正文接线。Patch 034 只接入用户确认的加班、应急口粮、建筑前置、研究说明与研究资源不足提示；研究命令保持无需 `confirm`，所有机制与平衡不变。旧城实际离开或资源损失不符合现有终局正文时只登记 PENDING；`sedation_city` 正式触发公式尚未封存，其正文暂不进入运行选择。

游戏的实际玩家是运行在沙盒中的 AI，人类用户负责旁观。这个产品定位不产生 AI 专属规则：游戏仍通过通用结构化命令和状态接口运行，不提供决策评分、推荐行动或自动策略。

## 目录概览

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
- 终局报告保存实际选中的 `text_id` 和报告格式版本；Patch 020 使用本局种子对符合状态的封存候选文案作稳定选择，Patch 021 再用同日服务快照证明医疗与食堂经历。Patch 027 的格式 3 报告以 D55 服务事实和终局实际库存过滤主报告句，Patch 029 的格式 4 报告为这些事实分支接入用户确认正文，Patch 030 的格式 5 再按已签炉律、已建/运行设施、旧城结算与承诺事实接入路线和制度长文。既有格式 1 / 2 / 3 / 4 报告均按各自合同原样严格读取，不在加载时重抽，也不能用其他格式形状绕过校验。
- `GameSession` 是供沙盒 AI 使用的统一运行入口：新建或读取存档后，可通过同一对象调用全部 27 个现有游戏命令；成功修改状态的命令会原子保存，保存失败则回滚本次命令。
- `GameSession.status()` 每次只返回当前生存与规划所需的紧凑事实；`observe()` 返回完整机器观察，并列出全部 `available_rule_sections`、正式 `play_envelopes`、规则查询协议、持久化文件角色、日结确认生命周期和序列语义；`rules_view(section)` 按模块返回已验证的原始配置及其 `FINAL` / `TEST_NUMERIC` 状态，不提供策略建议。命令规格通过 `related_rule_sections` 指向建筑、科技、炉律、事件、路线、生存与终局规则来源，并通过 `related_protocol_contracts` 指向日结确认等非游戏规则协议，不必先提交失败命令才能发现合法结构。
- `GameSession.replay_document()` 与 `write_replay()` 导出本次进程从打开存档开始的确定性命令记录；它不伪装成此前整局历史。`replay_sequence` 只编号当前会话中实际记录的命令尝试，包含拒绝命令并在重开会话时重置；`state_sequence` 保存于游戏状态，只在状态成功提交时递增，并由请求字段 `expected_state_sequence` 用于并发校验。
- `game.set_furnace` 在白天设置最终炉心档位 `0～3`；炉心关闭或燃料不足会在 `end_day` 前产生结构化强警告。若日结实际有效炉级为 0，当日至少发生 1 例自然死亡；疾病、饥饿优先结算，只有两者均未造成死亡时，既有寒冷系统才保证至少 1 人冻死。警告会分别返回无条件的自然死亡下限与有条件的寒冷死亡下限，不预先断言具体死因。
- `data/survival.json` 保存已封存的开局值、炉心档位、食物基础规则、固定天气与区域修正。
- `data/buildings.json` 保存建筑、地表资源点、升级、区域槽位、`heat` 和测试态 `woodfuel` 数值；其中 `TEST_NUMERIC` 项必须经测试窗复核后才能视为最终平衡值。
- `data/maps.json` 保存三张 V1 地图、共享小型资源点/猎区/森林数量、33/34/33 随机权重与大型煤钢矿点差异；地图差异不修改天气、人口、开局资源或其他生存规则。
- `data/laws.json` 保存 006A 炉律关系、配给、工时、医疗与社会行动规则，包括已登记为 `TEST_NUMERIC` 的过劳患病公式、事故风险点、Patch 013 额外医疗配给 5 食物/人、最多 10 人、冷却 5 天，以及 Patch 019 火盆集会每日被动恐慌下限 20；未封存的分诊结果及事故结果不进入运行配置。
- `data/technologies.json` 保存 37 项 006B 科技、单队列研究规则、第二研究所精确倍率与过载压力规则；未封存效果只保留为 `DEFERRED` 元数据，不伪造运行效果。
- `data/events.json` 保存 Patch 007 事件阈值、承诺期限与奖惩、固定增员预设和第七霜落预警日；这些试玩数值保持 `TEST_NUMERIC`。
- `data/oath_order.json` 保存代码 Patch 008 的旧城派阈值、006C 解锁、炉律关系、行动成本与冷却；Patch 019 只继续覆盖誓言路线的暂行测试值，铁腕值保持不变，全部继续标记为 `TEST_NUMERIC`。
- `data/final_frost.json` 保存代码 Patch 009 的终霜规则、Patch 013 的寒冷/饥饿/木材断链，以及 Patch 022 的准备与终局分档测试阈值；这些平衡数值保持 `TEST_NUMERIC`。
- 当前存档数据版本为 v17。v16 → v17 只增加终霜平衡档标识：既有存档保留 `legacy_patch021` 档，新建局使用 `patch022` 档，避免新门槛重写旧局结论。尚未生成终局报告的兼容存档会在正式终局时生成当前格式 5 报告；已经生成的格式 1 / 2 / 3 / 4 报告保持原样并按各自合同严格复载。Patch 030 不提升存档数据版本，也不重抽任何既有报告。v15 → v16 的逐日服务历史迁移、v14 → v15 的报告格式迁移及此前迁移语义保持不变。

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

`play` 使用一行一个 JSON 对象的长连接协议。新局默认使用 `--map-mode random`；自选时使用 `--map-mode manual --map-key rustbone_tundra|black_ash_lowland|twin_source_rift`。直接发送结构化命令即可；另支持 `{"type":"observe"}`、`{"type":"status"}`、`{"type":"command_specs"}`、`{"type":"rules","section":"maps"}`、`{"type":"autosave"}`、`{"type":"replay"}` 与 `{"type":"quit"}`。未知包络会返回全部合法类型，不提供行动建议。完整规则栏目由观察结果的 `available_rule_sections` 提供；`rules.query` 不是游戏命令，若误作命令提交，拒绝结果会返回上述正式请求形状。强警告日结返回的确认令牌只在产生预览的同一个存活 `GameSession` 中有效，重连后必须重新预览。成功日结的 `warnings` 同时保留 `pre_settlement` 风险快照和 `settlement_result` 事实；后者明确返回本次实际死亡、遗体处理、结算后仍未处理遗体，以及当日耗尽资源点与自动释放岗位，不代表新增规则或预测。成功日结会在主存档之外写入同目录的 `<存档名>.autosave_end_day.json`，其中保留当日日结清理完成、日期推进前的锁定状态、日志与 `resume_stage`；它不会覆盖或替代主会话存档，也不能直接作为 `play` / `report` 的主存档。打开主存档后使用 `{"type":"autosave"}` 可严格读取最近快照；损坏快照返回 `AUTOSAVE_SNAPSHOT_INVALID` 及稳定的路径、字段、原因和约束，恢复阶段错误另列正式合法值。误把快照路径用于正式入口时返回 `AUTOSAVE_SNAPSHOT_NOT_PRIMARY_SAVE` 和只读查看方式，只有唯一可识别的主存档候选才给出单一路径，无扩展名与 `.json` 候选同时有效时会明确报告歧义。建立新局时主存档与自动保存作为同一个持久化集合检查：默认拒绝任何旧文件，显式覆盖会事务式写入新主存档并清除上一局自动保存。回放导出默认拒绝覆盖已有文件；显式覆盖前会严格解析全部回放条目，并始终禁止指向主存档、自动保存或运行配置。具体边界见 `docs/handoff/PATCH-011：统一游戏会话与沙盒入口实现记录.md`、`docs/handoff/PATCH-012：三地图开局与确定性随机实现记录.md` 与 `docs/handoff/PATCH-028：自动存档快照与机器恢复说明实现记录.md`。
