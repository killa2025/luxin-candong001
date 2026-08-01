# 炉心残冬

《炉心残冬》项目仓库。

代码 Patch 013 已并入 `main`，补齐 D1～D55 寒冷暴露、四层饥饿、饥饿疾病/重症/死亡与社会压力、D49 木材供应链锁死，以及更保守的额外医疗配给试玩数值。当前 Patch 014 只修复盲玩发现的日结食物强预警误报：预警会在状态副本上复用正式建筑生产和食堂加工逻辑，计入当日真正可运行的狩猎小屋、温室与食堂产出；停炉或低温导致设施停摆时仍保留真实缺粮警告。誓言、铁腕、医疗、住房及资源平衡未在本补丁调整。

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
- `game.end_day` 与 `game.confirm_end_day` 执行固定阶段日结；Patch 007 在推进到新一天后先结算承诺，再按 1 重大 + 1 普通或 2 普通的上限生成事件。
- `game.resolve_old_city_event` 处理旧城派固定阶段事件；未处理的旧城派阶段事件会硬阻断日结。
- `game.sign_oath_order_law`、`game.staff_oath_order_facility` 与 `game.use_oath_order_action` 分别处理 006C 签署、守炉堂/巡查所派驻及路线主动行动；两条路线永久互斥，特殊设施自动启用、零槽位且不通过 `build` 建造。
- `game.resolve_event` 处理当前可执行事件选项；重大事件未处理时硬阻塞日结，普通事件允许忽略且不会在后台偷偷结算。
- `game.end_run` 只允许在 D55 完整结算、评分和报告已经生成后以 `confirm=true` 主动封存本局；它保留原 `ending_id`、评分和标签，只另记 `run_state=ended` 与 `termination_reason=player_ended`。
- `GameSession` 是供沙盒 AI 使用的统一运行入口：新建或读取存档后，可通过同一对象调用全部 27 个现有游戏命令；成功修改状态的命令会原子保存，保存失败则回滚本次命令。
- `GameSession.status()` 每次只返回当前生存与规划所需的紧凑事实；`observe()` 返回完整机器观察；`rules_view(section)` 按模块返回已验证的原始配置及其 `FINAL` / `TEST_NUMERIC` 状态，不提供策略建议。
- `GameSession.replay_document()` 与 `write_replay()` 导出本次进程从打开存档开始的确定性命令记录；它不伪装成此前整局历史。
- `game.set_furnace` 在白天设置最终炉心档位 `0～3`；炉心关闭或燃料不足会在 `end_day` 前产生结构化强警告。
- `data/survival.json` 保存已封存的开局值、炉心档位、食物基础规则、固定天气与区域修正。
- `data/buildings.json` 保存建筑、地表资源点、升级、区域槽位、`heat` 和测试态 `woodfuel` 数值；其中 `TEST_NUMERIC` 项必须经测试窗复核后才能视为最终平衡值。
- `data/maps.json` 保存三张 V1 地图、共享小型资源点/猎区/森林数量、33/34/33 随机权重与大型煤钢矿点差异；地图差异不修改天气、人口、开局资源或其他生存规则。
- `data/laws.json` 保存 006A 炉律关系、配给、工时、医疗与社会行动规则，包括已登记为 `TEST_NUMERIC` 的过劳患病公式、事故风险点及 Patch 013 额外医疗配给 5 食物/人、最多 10 人、冷却 5 天；未封存的分诊结果及事故结果不进入运行配置。
- `data/technologies.json` 保存 37 项 006B 科技、单队列研究规则、第二研究所精确倍率与过载压力规则；未封存效果只保留为 `DEFERRED` 元数据，不伪造运行效果。
- `data/events.json` 保存 Patch 007 事件阈值、承诺期限与奖惩、固定增员预设和第七霜落预警日；这些试玩数值保持 `TEST_NUMERIC`。
- `data/oath_order.json` 保存代码 Patch 008 的旧城派阈值、006C 解锁、炉律关系、行动成本与冷却；第六批补表数值统一保持 `TEST_NUMERIC`。
- `data/final_frost.json` 保存代码 Patch 009 的终霜规则及 Patch 013 的寒冷、饥饿、木材断链与食物评分阈值；新增平衡数值保持 `TEST_NUMERIC`。
- 当前存档数据版本为 v14；在 v13 地图状态之外，新增四层饥饿及整数余数、寒冷暴露余数、绑定结算日的无房人口寒冷快照、D49 木材供应快照、全局/终霜饥饿统计和终局限制因素。v13 → v14 不伪造旧局未曾保存的未进食人数；含旧终霜记录的整段终霜继续按 v13 食物评分语义校验，同时单独登记迁移记录日期，使迁移后新结算日仍严格使用 v14 死亡分配规则。

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

`play` 使用一行一个 JSON 对象的长连接协议。新局默认使用 `--map-mode random`；自选时使用 `--map-mode manual --map-key rustbone_tundra|black_ash_lowland|twin_source_rift`。直接发送结构化命令即可；另支持 `{"type":"observe"}`、`{"type":"rules","section":"maps"}`、`{"type":"replay"}` 与 `{"type":"quit"}`。成功日结会在主存档之外写入同目录的 `<存档名>.autosave_end_day.json`，其中保留当日日结清理完成、日期推进前的锁定状态、日志与 `resume_stage`；它不会覆盖主会话存档。建立新局时主存档与自动保存作为同一个持久化集合检查：默认拒绝任何旧文件，显式覆盖会事务式写入新主存档并清除上一局自动保存。回放导出默认拒绝覆盖已有文件；显式覆盖前会严格解析全部回放条目，并始终禁止指向主存档、自动保存或运行配置。具体边界见 `docs/handoff/PATCH-011：统一游戏会话与沙盒入口实现记录.md` 与 `docs/handoff/PATCH-012：三地图开局与确定性随机实现记录.md`。
