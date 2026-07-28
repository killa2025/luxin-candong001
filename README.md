# 炉心残冬

《炉心残冬》项目仓库。

当前仓库已完成代码 Patch 010：在 Patch 009 的 D49～D55 第七霜落、六系统评分和结局标签之上，接入可保存、可严格校验的结构化终局报告、`game.end_run` 主动封存命令及命令行报告入口。未封存的候选池条件、死亡记录句、零霜落死亡替代文案和图形界面仍保持 PENDING，不进入正式报告。

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
- `game.set_furnace` 在白天设置最终炉心档位 `0～3`；炉心关闭或燃料不足会在 `end_day` 前产生结构化强警告。
- `data/survival.json` 保存已封存的开局值、炉心档位、食物基础规则、固定天气与区域修正。
- `data/buildings.json` 保存建筑、地表资源点、升级、区域槽位、`heat` 和测试态 `woodfuel` 数值；其中 `TEST_NUMERIC` 项必须经测试窗复核后才能视为最终平衡值。
- `data/laws.json` 保存 006A 炉律关系、配给、工时、医疗与社会行动规则，包括已登记为 `TEST_NUMERIC` 的过劳患病公式与事故风险点；未封存的分诊结果及事故结果不进入运行配置。
- `data/technologies.json` 保存 37 项 006B 科技、单队列研究规则、第二研究所精确倍率与过载压力规则；未封存效果只保留为 `DEFERRED` 元数据，不伪造运行效果。
- `data/events.json` 保存 Patch 007 事件阈值、承诺期限与奖惩、固定增员预设和第七霜落预警日；这些试玩数值保持 `TEST_NUMERIC`。
- `data/oath_order.json` 保存代码 Patch 008 的旧城派阈值、006C 解锁、炉律关系、行动成本与冷却；第六批补表数值统一保持 `TEST_NUMERIC`。
- `data/final_frost.json` 保存代码 Patch 009 的终霜日历、停工、伤害、准备、评分和标签规则；第七批补表中的试玩数值保持 `TEST_NUMERIC`。
- 当前存档数据版本为 v12；在 v11 的 D49 基线、终霜每日记录、D55 评分与标签之外，新增运行终止状态和结构化报告 text_id 选择。v11 → v12 对未终局存档使用未终止、未生成报告的安全默认值，对已有可验证终局结果的存档确定性补建结构化报告；既有 v10 → v11 的可重建边界保持不变。

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
```

Patch 010 的终局报告与主动封存边界见 `docs/handoff/PATCH-010：终局报告与主动结束实现记录.md`。此前 Patch 的实现记录仍保存在 `docs/handoff/`。
