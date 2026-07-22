# 运行配置目录

本目录保存《炉心残冬》的数值、建筑、科技与文案等运行配置。

`survival.json` 保存已封存的普通难度开局值、基础食耗、炉心档位、固定天气与区域温度修正。`buildings.json` 保存建筑目录、地表资源点、区域槽位、升级、`heat` 与测试态 `woodfuel` 数值。`laws.json` 保存 006A 炉律关系、配给、工时、医疗与社会行动规则。Patch 006 新增 `technologies.json`，保存 37 项 006B 科技、研究成本与天数、单队列研究规则、第二研究所倍率和过载压力规则；测试数值声明为 `TEST_NUMERIC`，未封存科技效果只登记为 `DEFERRED`，不伪装成运行效果。正式运行配置必须：

- 使用 UTF-8 编码（兼容有无 BOM）和标准 JSON；`NaN`、`Infinity`、`-Infinity` 均为非法值；
- 顶层必须是 JSON 对象，并声明合法且可运行的 `config_status`；缺失、未知、类型错误或非运行状态均拒绝加载；
- 不包含 `terminal_fail`、`trust_fail`、`panic_fail`、`hope_state` 等作废字段；
- 键和值均不包含 `PENDING_*`、`DEPRECATED`、`TODO_TEXT`、`TODO_VALUE`、`TODO_SYSTEM`、`待确认`或`待判定`等非运行标记，也不得在这些标记后追加说明文字绕过校验；
- 未封存内容只登记在 `docs/PENDING.md`，不得伪装成运行值。

校验命令见仓库根目录 `README.md`。
