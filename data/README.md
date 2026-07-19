# 运行配置目录

本目录保存《炉心残冬》的数值、建筑、科技与文案等运行配置。

Patch 001 只新增不含游戏机制的 `manifest.json`，尚未录入数值、建筑、科技或文案正文。正式运行配置必须：

- 使用 UTF-8 编码（兼容有无 BOM）和标准 JSON；`NaN`、`Infinity`、`-Infinity` 均为非法值；
- 顶层必须是 JSON 对象，并声明合法且可运行的 `config_status`；缺失、未知、类型错误或非运行状态均拒绝加载；
- 不包含 `terminal_fail`、`trust_fail`、`panic_fail`、`hope_state` 等作废字段；
- 键和值均不包含 `PENDING_*`、`DEPRECATED`、`TODO_TEXT`、`TODO_VALUE`、`TODO_SYSTEM`、`待确认`或`待判定`等非运行标记，也不得在这些标记后追加说明文字绕过校验；
- 未封存内容只登记在 `docs/PENDING.md`，不得伪装成运行值。

校验命令见仓库根目录 `README.md`。
