# 炉心残冬

《炉心残冬》项目仓库。

当前仓库已完成代码 Patch 002：在 Patch 001 的机器可读状态、统一可复现随机源、配置与文案注册、结构化命令、日志及回放接口之上，建立固定顺序的 `end_day` 日结编排。当前只实现流程与安全边界，尚未实现各阶段的资源、人口、建筑、温度、炉律、科技、事件或终局算法。

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
- `game.end_day` 与 `game.confirm_end_day` 提供 Patch 002 的机器可读日结入口；日结按固定阶段运行，具体资源、人口、建筑、炉律、科技、事件与终局算法由后续 Patch 接入。

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

Patch 002 的日结编排、风险分级、自动保存接口与施工边界见 `docs/handoff/PATCH-002：日结主流程实现记录.md`。Patch 001 的交付范围、字段与边界见 `docs/handoff/PATCH-001：实现记录.md`。Patch 000 的技术决策、边界和冲突处理记录见 `docs/handoff/PATCH-000：仓库初始化与施工规则验证.md`。
