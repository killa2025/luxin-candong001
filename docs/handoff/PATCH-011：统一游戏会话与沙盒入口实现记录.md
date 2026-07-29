# PATCH-011：统一游戏会话与沙盒入口实现记录

## 一、目标

Patch 001～010 已经具备机器状态、结构化命令、日结、建筑、炉律、科技、事件、旧城派、第七霜落、终局评分和报告，但此前没有一个正式入口把这些系统装配成可持续游玩的同一局。

Patch 011 只补运行外壳：

- 统一装配全部现有系统；
- 新建、读取和原子保存一局游戏；
- 路由全部现有结构化命令；
- 每次返回紧凑状态；
- 提供完整观察、配置查看和本次会话回放；
- 提供适合沙盒 AI 长连接调用的 JSON Lines 命令行入口。

本 Patch 不新增游戏机制、AI 专属规则、评分建议、推荐行动或自动策略。

## 二、外部参考的采用边界

本轮阅读了 `tutusagi/ai-fishing-game` 的公开 README、工具 Schema、代码执行示例和引擎入口。仅采用以下通用产品思路：

- 对 AI 只暴露稳定的单一运行入口；
- 状态独立保存在磁盘，不依赖对话上下文；
- 每次行动附带紧凑状态，减少重复观察；
- 同一随机种子和同一指令序列可复现；
- 批量内容和完整规则按需读取，避免每次返回全部资料。

没有复制其代码、数值、文案、鱼类数据、概率、存档格式或盲玩打包方案。《炉心残冬》继续使用自身既有的结构化命令、存档版本和确定性随机系统。

## 三、统一 Python 入口

公开入口：

```python
from furnace_winter import GameSession

game = GameSession.open(
    "furnace_winter_save.json",
    config_dir="data",
    seed=2025,
)
```

核心方法：

- `GameSession.new(...)`：建立新局；已有存档默认拒绝覆盖；
- `GameSession.load(...)`：严格读取现有存档；
- `GameSession.open(...)`：存在则读取，不存在则建立；
- `command(name, arguments)`：便捷执行一个现有结构化命令；
- `execute(request)`：执行完整 `CommandRequest`；
- `execute_payload(payload)`：执行 JSON 对象形式的命令；
- `status()`：返回紧凑、无策略含义的当前事实；
- `observe()`：返回完整 `Observation`；
- `rules_view(section)`：读取一个已验证配置模块；
- `autosave_path`：读取与主存档隔离的 `autosave_end_day` 磁盘槽路径；
- `replay_document()` / `write_replay(path, overwrite=False)`：导出本次进程会话回放；已有目标默认拒绝覆盖。

`state` 属性返回深拷贝。外部修改该副本不会污染正式会话状态。

## 四、命令装配

统一目录登记 27 个既有命令：

- 日结：`game.end_day`、`game.confirm_end_day`；
- 生存：`game.set_furnace`；
- 建筑与派员：`game.build`、`game.upgrade`、`game.assign`、`game.unassign`、`game.assign_resource`、`game.unassign_resource`、`game.heat`、`game.woodfuel`；
- 炉律与社会行动：`game.sign_law`、`game.set_ration`、`game.set_worktime`、`game.overtime`、`game.medical_ration`、`game.triage`、`game.memorial`；
- 科技：`game.research`、`game.cancel_research`、`game.set_overload`；
- 事件：`game.resolve_event`；
- 旧城派与 006C：`game.resolve_old_city_event`、`game.sign_oath_order_law`、`game.staff_oath_order_facility`、`game.use_oath_order_action`；
- 终局：`game.end_run`。

命令仍由原系统负责合法性和事务校验。统一会话不重写任何机制规则。

## 五、存档与事务

- 新局会在 D1 初始化既有事件生成边界后保存；
- 成功且修改状态的命令自动写入指定存档；
- 使用同目录临时文件、刷新磁盘并原子替换正式存档；
- 配置感知的完整状态校验在写入前执行；
- 日结的 `AutosaveRecord` 会写入同目录的 `<存档名>.autosave_end_day.json`，保留 `settled_day`、日期推进前的锁定 `state`、日结 `logs` 与 `resume_stage`；主存档另行保存日期推进后的可继续游戏状态；
- 主存档与 `autosave_end_day` 是两个独立槽位，任何一方写入失败时都会恢复两者原有字节；
- 写入或最终校验失败时，本次命令回滚，返回 `INTERNAL_ERROR`；正式状态、旧存档、日结确认令牌、引擎最近自动保存及会话捕获记录均恢复到命令执行前；
- 拒绝、警告预览和其他未修改状态的结果不改写存档。

日结强警告的预览与确认必须发生在同一个 `GameSession` 中，这样既有确认令牌生命周期不会被错误绕过。

建立新局时，主存档与对应的 `autosave_end_day` 文件作为同一个持久化集合处理：

- 默认模式下，任一文件已经存在都会拒绝新建；只有自动保存残留而主存档不存在时也不会静默接入新局；
- `overwrite=True` 会事务式写入新 D1 主存档并清除上一局自动保存，不能把不同种子或日期的旧快照遗留给新局；
- 主存档写入或自动保存清理失败时，两份文件均恢复为新建前的原始字节；
- 即使显式覆盖，也不得把主存档指向 `manifest.json` 或任一已加载运行配置文件。

## 六、紧凑状态与数值查看

每次 `SessionExecution` 返回：

- 原始 `CommandResult`；
- 当前日、命令序号、终止状态；
- 人口、资源、仓储、炉心、信任、恐慌；
- 当前研究；
- 活跃事件、承诺和旧城待处理事件；
- 第七霜落及终局报告状态；
- 是否已写入存档。

`rules_view(section)` 支持：

- `survival`
- `buildings`
- `laws`
- `technologies`
- `events`
- `oath_order`
- `final_frost`

它返回仓库中的已验证原始配置和 `config_status`。因此现有数值并未缺失：

- `survival` 为 `FINAL`；
- 建筑、炉律、科技、事件、旧城派和终霜数值按原登记继续显示 `TEST_NUMERIC`；
- 科技中未封存效果继续显示 `DEFERRED`；
- `docs/PENDING.md` 中未封存公式仍不进入配置。

Patch 011 没有新增、调整或“补齐”任何平衡数值。

## 七、JSON Lines 沙盒入口

启动：

```text
python -m furnace_winter play furnace_winter_save.json --data-dir data --seed 2025
```

进程启动后先输出完整观察。此后每行输入一个 JSON 对象：

```json
{"name":"game.set_furnace","arguments":{"level":2}}
{"name":"game.end_day"}
{"type":"observe"}
{"type":"rules","section":"buildings"}
{"type":"replay"}
{"type":"quit"}
```

结构化命令可省略 `command_id` 和 `expected_state_sequence`，会话会生成稳定的本进程命令 ID，并默认绑定当前状态序号。需要并发保护的调用方仍可显式提供两者。

非法 JSON、非法外层消息、未注册命令和参数错误均返回稳定错误，不抛出游戏堆栈。

## 八、回放边界

回放记录包含：

- 打开会话时的初始状态快照；
- 本进程中的每个可记录命令；
- 命令结果；
- 随机状态前后边界；
- 日结结构化日志。

读取旧存档后，回放从该次打开的存档状态开始。它不是此前整局历史的伪造补录。跨进程整局回放持久化如需成为正式产品要求，应另行给出任务单。

`write_replay(...)` 的目标保护规则：

- 默认拒绝覆盖任何已有路径；
- 仅在 `overwrite=True` 且已有目标可严格识别为本项目回放文档时允许替换；
- 严格识别会逐项解析 `ReplayEntry` 的请求、结果、随机状态和日志，拒绝缺失或额外字段、非法类型、未知随机算法、非递增序号、日志乱序以及请求/结果 `command_id` 不一致；
- 无论是否允许覆盖，主存档、`autosave_end_day` 槽和八份运行配置文件均为受保护路径；
- 路径比较使用解析后的规范路径，不能用相对路径或等价路径绕过保护。

## 九、测试覆盖

新增测试覆盖：

- 27 个既有命令均被统一登记；
- `FINAL`、`TEST_NUMERIC` 和具体配置数值可按模块读取；
- 成功命令自动保存并可严格读回；
- 拒绝命令不改状态、不改存档；
- 保存失败完整回滚；
- 日结主存档写入失败时恢复确认令牌、引擎/会话自动保存和两个磁盘槽，原确认可安全重试；
- `autosave_end_day` 磁盘槽保持 D1 锁定状态及 `resume_stage=advance_day`，并与推进后的普通会话存档隔离；
- 覆盖新建会清除上一局自动保存，单独残留的自动保存默认阻止新建，清理失败会恢复主存档和自动保存原字节；
- 日结强警告预览与确认在同一会话中完成；
- 同种子、同指令得到相同状态和回放；
- 观察副本不能污染正式状态；
- 非法参数返回稳定错误；
- 回放可导出为规范 JSON；
- 回放默认拒绝覆盖已有文件，显式覆盖仅接受全部条目均严格合法的既有回放，并始终保护主存档、自动保存和全部运行配置；
- 非法条目、缺失字段、非法随机状态、错误序号、日志类型及请求/结果关联错误均拒绝覆盖且保持原文件字节；
- 新局显式覆盖也不能把存档写到运行配置路径；
- JSON Lines 入口可建立存档、执行命令并关闭；
- 盲玩反馈加固后，旧城派倒计时选项预览会显示选择后的倒计时和承诺目标/截止日，正式机器视图可持续查询承诺从生效到结算的生命周期，同时不暴露内部隐藏增长倒计时。

最终全量结果：328 项 `unittest` 通过；8 份 JSON 配置校验通过；`compileall` 与 `git diff --check` 通过。

## 十、越界自检

本轮未实现：

- 新游戏机制或新命令；
- PENDING 数值和公式；
- AI 决策评分、推荐行动或自动策略；
- 候选文案随机选择；
- 盲玩代码打包或源码隐藏；
- 图形、网页或桌面 UI；
- D56 或终局后继续模拟；
- Patch 012。
