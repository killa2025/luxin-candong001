# Patch 034：高频操作提示文案收口实现记录

## 1. 完成范围

本 Patch 只接入用户确认的 7 条玩家可见短提示：

- `confirm.action.overtime_day.body`；
- `confirm.action.emergency_ration.body`；
- `building.hospital.missing_requirement_hint`；
- `building.greenhouse.upgrade_missing_requirement_hint`；
- `building.house.upgrade_missing_requirement_hint`；
- `research.confirm.body`；
- `research.resource.not_enough`。

七条文字进入正式 `TextRegistry`，状态为 `FINAL`。加班日与应急口粮在既有确认拒绝中返回确认正文；医院双前置同时缺失、温室升级科技缺失及住宅升级科技缺失时返回对应条件提示；研究资源不足时返回实际缺口正文。研究开始说明同时进入正式命令规格和科技规则查看结果。

本 Patch 不修改炉律、配给、工时、建筑、升级、科技、研究、资源、冷却、事故、存档或平衡规则，不开始 Patch 035。

## 2. 用户确认文字（逐字核验依据）

### `confirm.action.overtime_day.body`

> 确认让「{building_name}」执行加班日？本日不可取消；普通生产提高至两倍，医疗与研究进度提高至 1.5 倍，但信任 -2、恐慌 +3，并会新增患病者与事故风险。

### `confirm.action.emergency_ration.body`

> 确认启用应急口粮？本日人均食物消耗降至一半，信任 -3、恐慌 +4；只持续当天，随后恢复此前配给，四天内不能再次使用。

### `building.hospital.missing_requirement_hint`

> 医院尚未解锁。需要先签署「基础医疗法」，并完成「医院标准化」研究。

### `building.greenhouse.upgrade_missing_requirement_hint`

> 温室还不能升级。需要先完成「温室改良」研究。

### `building.house.upgrade_missing_requirement_hint`

> 这座住宅还不能升级。需要先完成「{required_tech_name}」研究。

### `research.confirm.body`

用户确认采用兼容口径，不为既有 `game.research` 新增强制确认。正式正文改为执行前说明：

> 开始研究「{technology_name}」时，木材 {wood_cost}、钢材 {steel_cost} 将立即扣除；同一时间不能进行其他研究。

### `research.resource.not_enough`

> 当前资源不足，无法开始这项研究。还缺少：{missing_resources}。

## 3. 机器接口

- `game.overtime` 仍只接受明确的 `confirm=true`；省略确认时返回 `confirmation_text_id` 与插入正式建筑名称的 `confirmation_text`。命令规格同时公开文字模板与参数来源。
- `game.set_ration` 选择 `emergency` 且省略确认时，返回应急口粮确认正文。其他配给模式不显示该正文。
- `game.build` 仅在医院的基础医疗法与医院标准化科技同时缺失时返回双前置提示，原有 `missing_law_ids`、`missing_tech_ids` 保持不变。
- `game.upgrade` 对温室与两级住宅升级返回对应科技提示；住宅正文插入本次实际需要的科技名称。
- `game.research` 的参数和执行合同不变，不新增 `confirm`。`command_specs` 与 `rules_view("technologies")` 公开非确认性质的扣费和单队列说明。
- 研究资源不足仍返回稳定的 `missing_resources`，并新增 `feedback_text_id` 与按实际木材、钢材缺口渲染的 `feedback_text`。
- 所有拒绝继续保持 `state_changed=false`，不修改状态、存档或序列。

## 4. 验证范围

- 七个 `text_id` 逐字注册为玩家可见 `FINAL` 文本，来源指向本实现记录；
- 加班日和应急口粮确认正文逐字返回且拒绝不改变状态；
- 医院、温室和两级住宅的前置条件提示与结构化缺口一致；
- 研究说明可从命令规格及科技规则中发现，且 `game.research` 继续无需 `confirm`；
- 研究木材、钢材不足正文按本次实际缺口稳定渲染；
- 全量测试、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均须通过。

## 5. 仍然 PENDING

- 分级救治完整确认正文及其正式结果数值；
- 取消研究确认正文；
- 其他建筑、炉律、科技和路线条件的未确认专属提示；
- 正式终局随机权重、图形 UI、D56 与 postgame；
- 其余 `docs/PENDING.md` 登记的未封存机制与数值。

完成后停止，不开始 Patch 035。
