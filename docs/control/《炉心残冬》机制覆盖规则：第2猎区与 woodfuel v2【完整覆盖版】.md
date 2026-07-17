## 《炉心残冬》机制覆盖规则：第2猎区与 woodfuel v2【完整覆盖版】  
本文件覆盖：  
1. 《机制覆盖规则：第2猎区与 woodfuel v0【确认前草案】》  
2. 《机制覆盖规则：第2猎区与 woodfuel v1【用户确认版】》  
3. 《机制覆盖规则：第2猎区与 woodfuel v1-r1 小修覆盖块》  
本版为完整覆盖版。 本文件不修改旧封存正文。 本文件不新增测试窗任务。 本文件不补未封存数值。 本文件只封存用户已确认的机制方向，并把仍未封存的数值标为 PENDING。  
   
⸻  
   
## 一、本版确认内容  
本版正式采用：  
```
第2猎区：
第一座狩猎小屋建成后自动开放。

woodfuel：
进入 V1。
定位为应急燃料。
必须玩家手动确认开启。
当日生效，日结后自动关闭。
次日若仍需使用，必须再次手动确认。
转换效率远低于煤炭。
不能替代煤炭。
不进入煤炭库存。
不支付 heat。
不支付 overload。
不改变炉心档位煤耗。
不改变今日完整日耗公式。

```
仍未封存：  
```
woodfuel_conversion_ratio = PENDING_NUMERIC
woodfuel_daily_limit = PENDING_NUMERIC
woodfuel_minimum_unit = PENDING_NUMERIC
woodfuel_cooldown = PENDING_NUMERIC_OR_NONE

```
   
⸻  
   
## 二、第2猎区正式覆盖规则  
## 2.1 基础口径  
保持已封存基础：  
1. 开局可用猎区：1。  
2. 地图总猎区：2。  
3. 单个猎区支持 1 座狩猎小屋。  
4. 狩猎小屋建筑上限 = 当前可用猎区数量。  
5. 猎区不设置资源上限。  
6. 猎区不因狩猎次数枯竭。  
7. 猎区不因累计产出枯竭。  
8. 猎区本身不占普通区域槽位。  
9. 狩猎小屋作为建筑，占用外环槽位。  
10. 第2猎区开放后，只改变当前可用猎区数量，不新增猎区储量系统。  
   
⸻  
   
## 2.2 第2猎区开启方式  
正式采用：  
```
第一座狩猎小屋 build 成功后，第2猎区自动开放。

```
规则：  
```
开局只开放第1猎区。
当玩家建成第一座狩猎小屋后，第2猎区自动开放。
第2猎区开放后，当前可用猎区数从 1 变为 2。
狩猎小屋建筑上限随当前可用猎区数同步提高。

```
触发条件：  
```
first_hunting_lodge_built = true

```
触发时机：  
```
第一座狩猎小屋 build 成功后。

```
推荐接线：  
```
当第一座狩猎小屋建成：
  if second_hunting_area.available == false:
      second_hunting_area.available = true
      available_hunting_area_count = 2
      hunting_lodge_max_count = 2

```
   
⸻  
   
## 2.3 第2猎区不需要的内容  
第2猎区开放不需要：  
1. 额外工程科技树前置。  
2. 额外普通适配城约前置。  
3. 额外誓言与铁腕炉约前置。  
4. 随机事件。  
5. 固定日期。  
6. 新探索命令。  
7. 前哨系统。  
8. 地图派遣系统。  
9. 额外资源消耗。  
10. 额外区域槽位。  
说明：  
这是最小机制补丁。 第2猎区只是地图已存在猎区容量的开放，不新增复杂地图系统。  
   
⸻  
   
## 2.4 玩家可见提示  
第一座狩猎小屋建成后，提示：  
```
猎手们沿着第一座狩猎小屋周边的风痕找到了更远的猎径。

第2猎区已开放。
当前可用猎区：2 / 2。
狩猎小屋上限提高至 2。

```
短版提示：  
```
第2猎区已开放：狩猎小屋上限提高至 2。

```
   
⸻  
   
## 2.5 面板显示  
建第一座狩猎小屋前：  
```
猎区：1 / 2 可用
狩猎小屋：0 / 1

```
建成第一座狩猎小屋后：  
```
猎区：2 / 2 可用
狩猎小屋：1 / 2

```
建成第二座狩猎小屋后：  
```
猎区：2 / 2 可用
狩猎小屋：2 / 2

```
   
⸻  
   
## 2.6 禁止写法  
不得写：  
```
总猎区 2 = 开局可建 2 座狩猎小屋。
第2猎区由随机事件开启。
第2猎区由未封存科技开启。
第2猎区由固定日期开启。
第2猎区需要新增探索系统。
第2猎区需要新增前哨系统。
猎区有储量。
猎区会枯竭。
猎区资源耗尽。
猎物越来越少。
狩猎小屋可以无限建造。

```
   
⸻  
   
## 三、woodfuel 正式覆盖规则  
## 3.1 正式定位  
woodfuel 进入 V1。  
正式定位：  
```
木头燃烧 / 应急燃料。

```
woodfuel 是：  
1. 应急燃料。  
2. 玩家主动确认的救急操作。  
3. 用木材低效补足炉心基础供暖的临时手段。  
4. 煤炭不足时的高代价保命出口。  
woodfuel 不是：  
1. 煤炭。  
2. 煤炭库存。  
3. 煤炭生产。  
4. 煤炭等价物。  
5. 采煤行动替代。  
6. 小型采煤机替代。  
7. heat 支付资源。  
8. overload 支付资源。  
9. 长期燃料路线。  
10. 免费翻盘按钮。  
   
⸻  
   
## 3.2 转换效率原则  
正式原则：  
```
woodfuel 转换效率远低于煤炭。
woodfuel 不能替代煤炭。

```
规则：  
1. woodfuel 效率必须劣于煤炭。  
2. woodfuel 不得 1:1 等价煤炭。  
3. woodfuel 不得优于煤炭。  
4. woodfuel 不得优于正常采煤。  
5. woodfuel 不得让木材变成稳定主燃料。  
6. woodfuel 不能让玩家长期不采煤也能安全运行。  
7. woodfuel 不能让第七霜落变成木材燃烧周。  
当前不封存具体转换比例。  
```
woodfuel_conversion_ratio = PENDING_NUMERIC

```
禁止写死：  
```
1 木材 = 1 煤炭
2 木材 = 1 煤炭
每日最多 40 木材
每日最多补 20 煤炭等价

```
这些数值未被本文件封存，不能进入代码窗。  
   
⸻  
   
## 3.3 手动确认规则  
woodfuel 必须由玩家手动确认开启。  
推荐命令方向：  
```
woodfuel
woodfuel on
burn wood
燃烧木材
开启木头燃烧

```
执行 woodfuel 必须弹出确认。 玩家确认后，当日 woodfuel 生效。 玩家取消后，不燃烧木材。  
确认弹窗固定为：  
```
你正在确认燃烧木材作为应急燃料。

木材资源有限，燃烧效率远低于煤炭且不能替代煤炭。

是否确认？

```
说明：  
1. 弹窗保持简短。  
2. 弹窗不额外解释 heat。  
3. 弹窗不额外解释 overload。  
4. 弹窗不额外解释煤炭库存。  
5. 弹窗不额外解释工程科技树。  
6. 内部规则保持清楚，不全部塞进 UI。  
   
⸻  
   
## 3.4 当日生效与次日状态  
正式规则：  
```
woodfuel 当日手动确认，当日生效。
日结后自动关闭。
次日若仍需燃烧木材，玩家必须再次手动确认开启。
woodfuel 不会跨日保持开启状态。
woodfuel 不会在煤炭不足时自动燃烧木材。

```
代码字段：  
```
woodfuel_next_day_state = manual_confirm_each_day

```
说明：  
1. woodfuel 是应急燃料，不是持续燃料模式。  
2. 每天是否燃烧木材，都必须由玩家主动确认。  
3. 系统不得在次日默认继续燃烧木材。  
4. 系统不得因煤炭不足静默消耗木材。  
5. 日结后自动关闭，避免连续误烧木材。  
   
⸻  
   
## 3.5 作用范围  
woodfuel 只作用于：  
```
炉心基础供暖日耗的临时补足。

```
woodfuel 不作用于：  
1. heat。  
2. overload。  
3. 建筑生产煤耗。  
4. 小型采煤机。  
5. 小型采钢机。  
6. 工程科技树研究。  
7. 事件支付。  
8. 终局评分中的煤炭库存本身。  
说明：  
woodfuel 可以帮助当日炉心基础供暖不至于完全断档。 但它不等于城市拥有了更多煤炭。  
   
⸻  
   
## 3.6 与煤炭库存的关系  
woodfuel 不进入煤炭库存。  
不得写：  
```
coal += converted_woodfuel

```
推荐内部字段：  
```
woodfuel_contribution_today

```
或：  
```
temporary_furnace_fuel_from_wood

```
结算时只用于判断炉心基础供暖支付是否被临时补足。  
示意：  
```
available_for_furnace_base_heating =
  coal_before_end_day
  + woodfuel_contribution_today

```
但煤炭库存本身仍只扣煤炭：  
```
coal_after_payment = coal_before_end_day - coal_paid

```
woodfuel 消耗木材：  
```
wood_after_payment = wood_before_end_day - wood_burned

```
说明：  
1. woodfuel 不是煤炭库存。  
2. woodfuel 不改变 coal 数值。  
3. woodfuel 只提供当日炉心基础供暖的临时燃料贡献。  
4. 终局统计煤炭库存时，不把已燃烧木材折算成煤炭余量。  
   
⸻  
   
## 3.7 与今日完整日耗的关系  
今日完整日耗仍按 008-3 基础规则：  
```
今日完整日耗 = 当前炉心档位基础煤耗 + 过载额外煤耗 - 炉心节煤科技修正

```
woodfuel 不改变今日完整日耗。  
woodfuel 只是在支付炉心基础供暖时，允许木材按低效比例临时补足基础供暖缺口。  
说明：  
1. woodfuel 不降低煤耗。  
2. woodfuel 不改变炉心档位煤耗。  
3. woodfuel 不改变炉心供暖修正。  
4. woodfuel 不降低过载额外煤耗。  
5. woodfuel 不改变 heat 成本。  
6. woodfuel 不改变工程科技树中的节煤效果。  
   
⸻  
   
## 3.8 与 heat 的关系  
woodfuel 不可支付 heat。  
保持：  
```
heat 单次耗煤 20。

```
不得写：  
```
heat 可用 woodfuel 支付。
木材燃烧可支付 heat。
woodfuel 自动补 heat 成本。

```
说明：  
1. heat 是关键建筑应急加热。  
2. woodfuel 是炉心基础供暖应急燃料。  
3. 两者不要混成一个系统。  
4. 如果玩家执行 heat 且煤炭不足，由 heat 系统提示无煤炭。  
5. woodfuel 不重复承担 heat 提示。  
   
⸻  
   
## 3.9 与 overload 的关系  
woodfuel 不可支付 overload。  
不得写：  
```
woodfuel 可支付过载额外煤耗。
木材燃烧可支撑 overload。
woodfuel 允许无煤过载。

```
说明：  
1. 过载是炉心高压操作。  
2. woodfuel 不能把“没有煤也能继续过载”变成可行路线。  
3. 如果 overload 煤炭不足或风险过高，由炉心 / 过载系统提示。  
4. woodfuel 不重复承担 overload 提示。  
   
⸻  
   
## 3.10 与炉心未开启提示的关系  
炉心未开启、炉心燃料不足、heat 无煤炭、overload 煤炭不足等，已有对应系统提示。 woodfuel 不重复承担这些提示。  
因此 woodfuel 确认弹窗不显示：  
```
当前炉心未开启，无法使用 woodfuel。
heat 不能用 woodfuel 支付。
overload 不能用 woodfuel 支付。
woodfuel 不进入煤炭库存。
woodfuel 不能支付 heat。
woodfuel 不能支付 overload。

```
说明：  
1. 这些仍是内部规则。  
2. 但不需要在 woodfuel 确认弹窗中重复显示。  
3. woodfuel 只提示“燃烧木材作为应急燃料”的核心风险。  
   
⸻  
   
## 3.11 与第七霜落的关系  
woodfuel 进入 V1 后，第七霜落期间仍必须保持高压。  
规则：  
1. woodfuel 可以作为短期救急。  
2. woodfuel 不能成为第七霜落稳定翻盘方案。  
3. woodfuel 不能替代前48天储煤。  
4. woodfuel 不能让第七霜落变成木材燃烧周。  
5. woodfuel 不能抵消第七霜落“炉心燃料压力极高”的定位。  
6. 第七霜落期间若使用 woodfuel，仍必须每日手动确认。  
7. 第七霜落期间 woodfuel 仍然日结后自动关闭。  
8. 第七霜落期间 woodfuel 仍不支付 heat / overload。  
   
⸻  
   
## 四、AI / 玩家提示要求  
## 4.1 D1 煤炭提示  
由于 woodfuel 进入 V1，但不能替代煤炭，D1 仍必须提示：  
```
当前煤炭 70。
炉心 1 档今日消耗 45。
若今日不安排采煤，明日炉心 1 档将出现燃料缺口。

可以通过今日采煤保障明日煤炭。
woodfuel 只是低效应急燃料，不能替代采煤。

```
说明：  
1. woodfuel 不应让 AI 玩家误以为 D1 可以不采煤。  
2. 今日采煤仍是保障明日炉心的主路径。  
3. woodfuel 只是高代价补救，不是主策略。  
   
⸻  
   
## 4.2 woodfuel 开启提示  
玩家执行 woodfuel 时，只显示：  
```
你正在确认燃烧木材作为应急燃料。

木材资源有限，燃烧效率远低于煤炭且不能替代煤炭。

是否确认？

```
   
⸻  
   
## 4.3 woodfuel 风险提示  
若玩家开启 woodfuel 后木材紧张，可在日结或资源提示中显示：  
```
木材燃烧消耗了建设与维修所需的木材储备。

```
不需要在确认弹窗里提前列出所有影响。  
   
⸻  
   
## 4.4 第2猎区提示  
建成第一座狩猎小屋后显示：  
```
第2猎区已开放：狩猎小屋上限提高至 2。

```
或完整显示：  
```
猎手们沿着第一座狩猎小屋周边的风痕找到了更远的猎径。

第2猎区已开放。
当前可用猎区：2 / 2。
狩猎小屋上限提高至 2。

```
   
⸻  
   
## 五、代码窗配置建议  
## 5.1 第2猎区配置  
```
hunting_area:
  total_count: 2
  available_count_start: 1
  depletes: false
  occupies_region_slot: false

second_hunting_area:
  exists: true
  available_at_start: false
  unlock_trigger: first_hunting_lodge_built
  effect:
    available_hunting_area_count: 2

hunting_lodge:
  max_count_source: current_available_hunting_area_count

```
   
⸻  
   
## 5.2 woodfuel 配置  
```
woodfuel:
  enabled: true
  type: emergency_fuel
  requires_manual_confirm: true
  active_duration: current_day_only
  next_day_state: manual_confirm_each_day
  auto_disable_after_end_day: true
  auto_burn_when_coal_shortage: false

  efficiency_worse_than_coal: true
  conversion_ratio: PENDING_NUMERIC
  daily_limit: PENDING_NUMERIC
  minimum_unit: PENDING_NUMERIC

  adds_to_coal_storage: false
  only_for_furnace_base_heating: true
  can_pay_heat: false
  can_pay_overload: false
  changes_furnace_coal_cost: false
  changes_daily_full_fuel_cost_formula: false

```
   
⸻  
   
## 5.3 woodfuel 支付示意  
示意逻辑：  
```
required_base_furnace_coal = furnace_base_cost_after_saving_tech
available_coal = coal_before_end_day

if woodfuel_confirmed_today:
    woodfuel_contribution_today = convert_wood_to_emergency_fuel(wood_burned)
else:
    woodfuel_contribution_today = 0

available_for_base_furnace =
    available_coal + woodfuel_contribution_today

```
注意：  
```
woodfuel_contribution_today 不写入 coal。
woodfuel_contribution_today 不支付 heat。
woodfuel_contribution_today 不支付 overload。

```
日结后：  
```
woodfuel_confirmed_today = false
woodfuel_contribution_today = 0

```
   
⸻  
   
## 六、仍未封存 / 不得代码窗猜  
以下仍未封存，不得自行补：  
```
woodfuel_conversion_ratio
woodfuel_daily_limit
woodfuel_minimum_unit
woodfuel_cooldown
woodfuel_UI_command_final_name
woodfuel_balance_with_D1_D3_coal_pressure

```
处理：  
1. 转换比例后续单独补数值。  
2. 每日上限后续单独补数值。  
3. 最小投入单位后续单独补数值。  
4. 冷却是否存在后续确认。  
5. 命令最终名可以先临时用 woodfuel。  
6. 平衡强弱交后续测试。  
   
⸻  
   
## 七、作废旧口径  
作废 v0 中以下推荐：  
```
woodfuel 暂不进入 V1 第一版正式代码。
只保留 future hook。
不显示给玩家。
不进入 AI 玩家策略。

```
改为：  
```
woodfuel 进入 V1。
woodfuel 是低效应急燃料。
woodfuel 必须手动确认。
woodfuel 当日生效，日结后自动关闭。
次日若仍需使用，必须再次手动确认。
woodfuel 不进煤炭库存。
woodfuel 不支付 heat / overload。
woodfuel 具体比例、每日上限、最小单位仍待补数值。

```
作废 v1 中以下内容：  
```
woodfuel_next_day_state = PENDING_SOURCE
次日是否自动关闭 / 日结后是否恢复，待源文件补查。
在 woodfuel 次日状态源文件未补查前，代码窗不得自行决定自动关闭或持续开启。

```
改为：  
```
woodfuel_next_day_state = manual_confirm_each_day
woodfuel 当日手动确认，当日生效，日结后自动关闭。
次日若仍需使用，必须再次手动确认。

```
作废过长弹窗：  
```
你正在确认燃烧木材作为应急燃料。

木材燃烧效率低于煤炭。
木材不会转化为煤炭库存。
木材燃烧不能支付 heat。
木材燃烧不能支付 overload。
木材燃烧会挤压住房、建筑、维修和后续建设所需木材。

是否确认？

```
改为短弹窗：  
```
你正在确认燃烧木材作为应急燃料。

木材资源有限，燃烧效率远低于煤炭且不能替代煤炭。

是否确认？

```
   
⸻  
   
## 八、禁止写法  
## 8.1 第2猎区禁止写法  
不得写：  
```
第2猎区开局可用。
总猎区 2，所以开局可建 2 座狩猎小屋。
第2猎区由随机事件自动开启。
第2猎区由未封存科技开启。
第2猎区需要新增探索系统。
第2猎区需要新增前哨系统。
猎区有储量。
猎区会枯竭。
狩猎小屋无限建造。

```
   
⸻  
   
## 8.2 woodfuel 禁止写法  
不得写：  
```
woodfuel 不进入 V1。
woodfuel 只是 future hook。
woodfuel 自动燃烧木材。
煤炭不足时默认自动用木材补。
woodfuel 跨日持续开启。
woodfuel 不需要每日确认。
woodfuel 1:1 等价煤炭。
woodfuel 优于煤炭。
woodfuel 进入煤炭库存。
woodfuel 可支付 heat。
woodfuel 可支付 overload。
woodfuel 改变炉心档位煤耗。
woodfuel 改变今日完整日耗公式。
woodfuel 替代采煤。
woodfuel 无上限。
woodfuel 让第七霜落变成木材燃烧周。

```
   
⸻  
   
## 九、给代码窗的摘要  
若后续代码窗需要本文件摘要，只能交以下内容：  
```
《机制覆盖规则：第2猎区与 woodfuel v2》代码窗摘要：

1. 第2猎区采用自动开放。
2. 开局可用猎区 1，总猎区 2。
3. 第一座狩猎小屋 build 成功后，第2猎区自动开放。
4. 第2猎区开放后，当前可用猎区数从 1 变为 2。
5. 狩猎小屋建筑上限 = 当前可用猎区数量。
6. 猎区不枯竭，不设置储量，不占普通区域槽位。
7. woodfuel 进入 V1。
8. woodfuel 是应急燃料，不是煤炭。
9. woodfuel 转换效率远低于煤炭。
10. woodfuel 不得 1:1 等价煤炭，不得优于采煤。
11. woodfuel 必须由玩家手动 confirm 开启木头燃烧。
12. woodfuel 当日手动确认，当日生效，日结后自动关闭。
13. 次日若仍需使用 woodfuel，必须再次手动确认。
14. woodfuel 不会跨日保持开启。
15. woodfuel 不会在煤炭不足时自动燃烧木材。
16. woodfuel 不进入煤炭库存。
17. woodfuel 只用于炉心基础供暖补足。
18. woodfuel 不可支付 heat。
19. woodfuel 不可支付 overload。
20. woodfuel 不改变炉心档位煤耗。
21. woodfuel 不改变今日完整日耗公式。
22. woodfuel 不替代采煤。
23. woodfuel_conversion_ratio = PENDING_NUMERIC。
24. woodfuel_daily_limit = PENDING_NUMERIC。
25. woodfuel_minimum_unit = PENDING_NUMERIC。
26. woodfuel 确认弹窗只显示：
    “你正在确认燃烧木材作为应急燃料。
    
    木材资源有限，燃烧效率远低于煤炭且不能替代煤炭。
    
    是否确认？”
27. woodfuel 不重复提示炉心未开启、heat 无煤炭、overload 煤炭不足等内容；这些由对应系统提示。

```
   
⸻  
   
## 十、本版结论  
本版确认：  
1. 第2猎区采用自动开放。  
2. 第一座狩猎小屋建成后，第2猎区开放。  
3. 第2猎区开放后，狩猎小屋上限提高到 2。  
4. 猎区不枯竭。  
5. 猎区不设置储量。  
6. woodfuel 进入 V1。  
7. woodfuel 是应急燃料。  
8. woodfuel 转换效率远低于煤炭。  
9. woodfuel 不能替代煤炭。  
10. woodfuel 不进入煤炭库存。  
11. woodfuel 不能支付 heat。  
12. woodfuel 不能支付 overload。  
13. woodfuel 不能替代采煤。  
14. woodfuel 必须玩家手动确认开启。  
15. woodfuel 当日生效，日结后自动关闭。  
16. woodfuel 次日若仍需使用，必须再次手动确认。  
17. woodfuel 不跨日保持开启。  
18. woodfuel 不自动燃烧木材。  
19. woodfuel 确认弹窗使用短提示。  
20. woodfuel 不重复提示炉心未开启、heat 无煤炭、overload 煤炭不足。  
21. woodfuel 具体转换比例、每日上限、最小投入单位仍未封存。  
22. 后续需要单独补 woodfuel 数值，并进行前3天煤炭 / 木材压力测试。  
   
⸻  
   
## 十一、自审表  
1. 是否覆盖 v0 / v1 / v1-r1：是。  
2. 是否采用第2猎区自动开放：是。  
3. 是否保留开局可用猎区 1：是。  
4. 是否保留总猎区 2：是。  
5. 是否保留猎区不枯竭：是。  
6. 是否让第2猎区开局可用：否。  
7. 是否把 woodfuel 写入 V1：是。  
8. 是否把 woodfuel 定位为应急燃料：是。  
9. 是否确认 woodfuel 每日手动确认：是。  
10. 是否确认 woodfuel 日结后自动关闭：是。  
11. 是否避免 woodfuel 自动燃烧木材：是。  
12. 是否避免 woodfuel 跨日持续开启：是。  
13. 是否让 woodfuel 当作煤炭库存：否。  
14. 是否让 woodfuel 1:1 等价煤炭：否。  
15. 是否补 woodfuel 具体转换比例：否。  
16. 是否让 woodfuel 支付 heat：否。  
17. 是否让 woodfuel 支付 overload：否。  
18. 是否确认 woodfuel 不改变今日完整日耗公式：是。  
19. 是否确认 woodfuel 不替代采煤：是。  
20. 是否把确认弹窗改短：是。  
21. 是否删除弹窗中过长的 heat / overload / 库存说明：是。  
22. 是否仍保留 heat / overload / 库存内部规则：是。  
23. 是否避免重复提示炉心未开启：是。  
24. 是否不写测试窗任务单：是。  
25. 是否列出仍未封存数值：是。  
