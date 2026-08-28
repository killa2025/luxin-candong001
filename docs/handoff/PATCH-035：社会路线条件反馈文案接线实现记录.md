# Patch 035：社会路线条件反馈文案接线实现记录

## 1. 范围

本 Patch 只把已经封存、并由用户确认进入本轮的社会路线条件正文接入正式机器反馈与 `oath_order` 规则视图：

- 首次选择誓言或铁腕路线时的互斥确认；
- 守炉堂、巡查所必须已启用且运行的条件；
- 炉约签署冷却及下一可签署日期；
- 近期死亡、旧城派危机和熟食条件不足提示。

不修改路线解锁、签署顺序、确认参数、设施启用与派员、行动成本、冷却天数、信任、恐慌、旧城派数值、存档或随机流。

## 2. 正式正文

以下正文保持原文语义并作为玩家可见 `USER_OVERRIDE` 注册：

| text_id | 正文 |
| --- | --- |
| `confirm.route.warning_mutual_exclusive` | 选择誓言路线后，铁腕路线及巡查所不会启用；选择铁腕路线后，誓言路线及守炉堂不会启用。 |
| `requirement.oath_hall.enabled_running` | 守炉堂必须已启用，并处于运行状态。 |
| `requirement.patrol_office.enabled_running` | 巡查所必须已启用，并处于运行状态。 |
| `cooldown.route.not_ready.feedback` | 誓言与铁腕炉约仍在冷却中。 |
| `cooldown.route.next_available_day` | 下一条炉律可在第 `{next_available_day}` 天签署。 |
| `requirement.old_city.active` | 旧城派危机已激活时可用。 |
| `requirement.cooked_food.enough` | 需要拥有足够熟食。 |
| `requirement.death_recent` | 仅在近期存在死亡事件时可用。 |

权威原始来源为：

- `docs/text-assets/第 3 轮：Route  Law  Mode  Confirm  Requirement  Cooldown.md`；
- `docs/control/《炉心残冬》全局修正总控正文【代码窗前置必读】.md`；
- 用户本轮确认的 Patch 035 接线范围。

原资产中的 `confirm.route.first_oath.body` 和 `confirm.route.first_iron.body` 含旧式 `confirm sign ...` 示例。本轮不把该旧命令写法接入正式机器反馈；结构化命令继续使用 `game.sign_oath_order_law` 与布尔参数 `confirm=true`。

## 3. 接口合同

- 首次路线炉律缺少确认时返回 `confirmation_text_id` 与 `confirmation_text`，拒绝不改变状态。
- 炉约仍在冷却时同时返回通用冷却正文、`next_available_day` 和动态日期正文。
- 终章炉律或路线行动因设施未运行而拒绝时，按路线返回守炉堂或巡查所条件正文。
- 悼亡钟、留城劝诫和需要熟食的行动分别返回与真实失败原因一致的条件正文。
- `rules_view("oath_order")` 提前公开上述确认、冷却和行动条件，供机器在提交前发现；不提供行动推荐或路线选择建议。

## 4. 测试

- 两条路线缺少首次确认时返回同一互斥正文，且不出现旧 `confirm sign` 写法；
- 冷却反馈动态插入真实下一可签署日期；
- 守炉堂、巡查所分别返回正确设施正文；
- 无近期死亡、旧城派未激活和熟食不足分别返回正确正文；
- 所有拒绝保持状态不变；
- 正式规则视图可发现正文、`text_id` 和 `confirm=true` 参数形状；
- 全量 unittest、9 份 JSON 配置校验、`compileall` 与 `git diff --check` 均须通过。

## 5. PENDING 与越界

- 分级救治完整确认正文及正式结果数值继续 PENDING；
- 取消研究提示及是否需要确认尚未封存，本轮不改变其协议；
- 终火誓约、最高戒令和路线设施的其他未确认叙事正文不自行补写；
- 社会路线所有 `TEST_NUMERIC` 值保持不变；
- 不实现 AI 策略、推荐行动、图形 UI、D56 或 Patch 036。

完成后停止，不开始 Patch 036。
