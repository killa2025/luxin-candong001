# Patch 033：事件与承诺反馈文案收口实现记录

## 1. 完成范围

本 Patch 只接入用户授权技术主窗定稿的 4 条玩家可见短提示：

- `event.option.unavailable.feedback`；
- `promise.same_type.active`；
- `promise.success.title`；
- `promise.failure.title`。

四条文字进入正式 `TextRegistry`，状态为 `FINAL`。事件选项不可用时，正式事件面板与命令拒绝结果返回通用提示；同类承诺已经存在时另返回明确原因文字；承诺正式结算时，`events.promise.settled` 日结日志返回与结果一致的标题 ID 和标题正文。

本 Patch 不修改事件选项、承诺创建条件、同类承诺上限、目标、期限、成功判定、奖惩、日结顺序、存档格式、随机性或任何平衡值；不开始 Patch 034。

## 2. 用户确认文字（逐字核验依据）

用户确认“这个你决定就好”，授权技术主窗采用此前给出的推荐稿。正式文字如下。

### `event.option.unavailable.feedback`

> 这个选项当前不可用。请查看返回的具体原因与所需条件。

### `promise.same_type.active`

> 同类型承诺仍在履行中。在它完成或失败以前，不能再次作出相同承诺。

### `promise.success.title`

> 承诺兑现

### `promise.failure.title`

> 承诺落空

## 3. 机器接口

- 不可用事件选项返回 `feedback_text_id`、`feedback_text`、稳定原因码以及可用时的 `reason_text_id`、`reason_text`；
- 同类承诺重复使用 `promise.same_type.active`，其他原因不伪造未确认的专属文案；
- 成功结算日志返回 `promise.success.title` / “承诺兑现”；
- 失败结算日志返回 `promise.failure.title` / “承诺落空”；
- 所有拒绝继续保持 `state_changed=false`，不改变存档、回放状态序列、承诺或事件状态。

## 4. 验证范围

- 四个 `text_id` 逐字注册为玩家可见 `FINAL` 文本，来源指向本实现记录；
- 同类承诺不可用面板及正式拒绝均返回通用提示和专属原因文字；
- 承诺成功、失败日结日志均返回与 outcome 一致的标题；
- 结算仍只发生一次，既有承诺状态、奖惩与日志事实不变；
- 全量 478 项 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均通过。

## 5. 仍然 PENDING

- 其他事件不可用原因的专属玩家文字；
- 守炉堂、巡查所、最终誓言与最高命令的其他未确认玩家正文；
- 建筑条件、确认框、研究及其他未封存玩家提示；
- 旧城派与社会路线 `TEST_NUMERIC` 平衡值的最终确认；
- `sedation_city` 正式触发公式；
- `children_lost` 正式阈值、学徒人口生成和其他未封存机制；
- 正式终局随机权重、图形 UI、D56 与 postgame。

完成后停止，不开始 Patch 034。
