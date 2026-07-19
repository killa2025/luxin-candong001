# 炉心残冬

《炉心残冬》项目仓库。

当前仓库已完成代码 Patch 003：在 Patch 001 的机器接口与 Patch 002 的固定 `end_day` 编排之上，接入人口、共享仓储、食物消耗、聚合住房、炉心基础支付和固定 55 天真实温度。当前可以从封存开局状态运行基础生存日结；建筑施工、岗位分配、`heat`、`woodfuel`、完整疾病与死亡、炉律、科技、事件、承诺及终局仍按后续 Patch 分批实现。

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
- `game.end_day` 与 `game.confirm_end_day` 执行固定阶段日结；Patch 003 已接入炉心支付、区域温度、食物与住房阶段。
- `game.set_furnace` 在白天设置最终炉心档位 `0～3`；炉心关闭或燃料不足会在 `end_day` 前产生结构化强警告。
- `data/survival.json` 保存已封存的开局值、炉心档位、食物基础规则、固定天气与区域修正。

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
```

Patch 003 的人口、资源、食物、住房、炉心基础及 PENDING 边界见 `docs/handoff/PATCH-003：人口资源食物住房炉心基础实现记录.md`。Patch 002 的日结编排见 `docs/handoff/PATCH-002：日结主流程实现记录.md`；Patch 001 的基础接口见 `docs/handoff/PATCH-001：实现记录.md`。
