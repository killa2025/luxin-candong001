# Patch 001 实现记录

## 交付结论

Patch 001 已完成项目基础状态与机器接口。本批没有实现游戏循环、建筑/炉心/资源结算、事件、炉律、科技、旧城、终局或任何 Patch 002 内容。

产品约束按用户确认登记为 `USER_OVERRIDE`：

1. 实际玩家是运行在沙盒中的 AI，人类用户旁观；不因此增加 AI 专属玩法、评分、推荐行动或自动策略。
2. 随机机制保留；所有未来随机调用必须统一经过可保存、可指定、可复现的随机源。
3. 相同初始状态、相同随机种子和相同行动序列必须产生相同结果。

## 已实现接口

- 机器可读 `GameState` 与 Patch 001 要求的全部子状态模型。
- `splitmix64-v1` 统一确定性随机流、种子指定、状态快照和恢复。
- `save_data_version`、状态编码/解码和逐版本迁移注册接口。
- `ConfigStatus`、JSON 配置读取与运行状态隔离。
- `TextRegistry`、缺失 `text_id` 报告、`PendingRegistry`、`DeprecatedRegistry`。
- 结构化命令请求、命令规格、参数类型校验、状态序列校验和玩法合法性回调接口。
- 结构化结果反馈、稳定错误码、无墙钟时间的日志与回放记录接口。
- `python -m furnace_winter state --seed <整数>` 最小机器启动入口。

Patch 001 不注册任何正式游戏命令；`available_commands` 当前为空。后续 Patch 只能在相应机制已封存后注册命令及其合法性规则。

## 状态字段

- `GameState`：`save_data_version`、`random`、`command_sequence`、`calendar`、`population`、`resources`、`furnace`、`buildings`、`laws`、`technologies`、`events`、`promises`、`old_city`、`final_result`。
- `CalendarState`：`current_day`、`max_day`、`current_phase`、`is_day_locked`、`is_end_day_confirmed`。
- `PopulationState`：总人口、存活/死亡及工人、工程师、儿童、两类学徒、失能/健康/患病/危重、无家/有住房人口字段。
- `ResourceState`：`coal`、`wood`、`steel`、`raw_food`、`cooked_food`、`storage_capacity`。
- `FurnaceState`：`is_active`、`mode_id`、`pressure`。
- `BuildingState`：任务单要求的建筑标识、类型、区域、槽位、建成/运行、人员分配、供暖与温度状态字段。
- `LawState`、`TechState`、`EventState`、`PromiseState`、`OldCityState`、`FinalResultState`：仅建立 ID、进度或结果容器，不含机制运算。
- `RandomState`：`seed`、`internal_state`、`draws`、`algorithm`。

未加入已废弃字段：`terminal_fail`、`trust_fail`、`panic_fail`、`hope_state`。

## 配置字段与文案登记

新增 `data/manifest.json`，字段为：

- `schema_version`
- `config_status`
- `configs`

本批没有把六轮文案正文导入运行数据，因此新增正式 `text_id` 数量为 0。测试使用的 `test.*` 标识只存在于测试代码，不属于正式运行文案。

`TextRegistry` 只接受 `FINAL`、`USER_OVERRIDE`、`TEST_NUMERIC` 且可见性为 `PLAYER_VISIBLE` 或 `COMMON` 的条目；`PENDING`、`TODO_TEXT`、`DEPRECATED`、内部文案和未决文案均被隔离。

## 新增代码文件

- `src/furnace_winter/models/`：状态、随机、序列化、存档与迁移。
- `src/furnace_winter/config/loader.py`、`status.py`：配置读取与状态枚举。
- `src/furnace_winter/text/`：文案、待定项和废弃项注册表。
- `src/furnace_winter/interface/`：观察、命令、校验、反馈、日志和回放接口。
- `tests/test_state_and_save.py`
- `tests/test_config_loader.py`
- `tests/test_text_registry.py`
- `tests/test_machine_interface.py`

## 验收边界

- 正式游戏机制：未实现。
- AI 决策评分、推荐行动、自动策略：未实现。
- 正式游戏命令：未注册。
- 正式文案资产：未导入。
- Patch 002：未开始。
