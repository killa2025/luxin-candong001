# PATCH-000：仓库初始化与施工规则验证

## 本轮结论

Patch 000 只建立可测试的工程骨架、配置校验入口和施工规则记录，不实现任何游戏机制。

## 最小技术方案

- 语言：Python 3.12。
- 运行依赖：仅 Python 标准库，当前无生产依赖。
- 测试：仓库内测试使用 `unittest` 编写，因此无需安装依赖即可执行；同时保持 pytest 兼容，并在 `pyproject.toml` 中将 pytest 声明为可选开发依赖。
- 代码布局：`src/furnace_winter/` 保存正式代码；`data/` 保存 JSON 配置；`tests/` 保存单元与回归测试；`docs/` 保存设计来源和施工依据。
- 分层方向：游戏逻辑、配置读取和未来 UI 保持分离；后续 UI 只能通过公开接口读取状态和提交命令。
- 可复现方向：后续 GameState、随机种子、事件历史和日志必须可序列化，以支持 D1～D55 自动模拟与回归。

## Patch 000 新增入口

```text
python -m unittest discover -s tests -t . -v
python -m furnace_winter validate-config data
```

第二条命令需要先以可编辑方式安装本项目，或在开发环境中把 `src/` 加入 Python 路径。pytest 安装后也可运行 `python -m pytest`。

## 配置校验边界

当前校验器只负责：

1. 遍历 `data/` 下的 JSON 文件。
2. 校验 UTF-8（兼容有无 BOM）和标准 JSON 格式，拒绝非有限数值。
3. 阻止作废字段进入正式运行配置。
4. 阻止 PENDING、DEPRECATED、TODO、待确认和待判定标记及其带说明形式进入正式运行配置。

当前校验器不负责：

- 定义 GameState；
- 导入正式数值或文案；
- 执行 `end_day`、炉律、科技、事件、旧城派或终局逻辑；
- 猜测任何未封存值。

## 冲突处理

- 仓库中的 `docs/control/`、`docs/numeric/`、`docs/text-assets/`、`docs/patches/` 与 `docs/handoff/`，按用户确认视为项目规则中旧目录名的现行对应目录。
- 守炉堂 / 巡查所的旧 `010` 描述已被高优先级资料覆盖，不进入实现。
- 第 2 猎区以完整覆盖版中的用户确认口径为准，但不属于 Patch 000 实现范围。

## 越界检查

本轮未实现：

- GameState 与各子状态模型；
- TextRegistry、PendingRegistry 或 DeprecatedRegistry；
- `end_day` 与任何游戏命令；
- 建筑、人口、资源、炉律、科技、事件、承诺、旧城派、第七霜落和终局机制；
- 正式数值、玩家文案和 UI。

上述内容从 Patch 001 或后续独立 Patch 开始，必须以对应任务单为准。
