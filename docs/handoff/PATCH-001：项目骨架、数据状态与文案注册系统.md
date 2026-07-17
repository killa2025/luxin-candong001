**PATCH-001：项目骨架、数据状态与文案注册系统**  
  
本轮目标  
  
建立可继续扩展的项目骨架。  
  
本轮不实现完整游戏循环，不实现完整 UI，不实现事件、炉律、科技、旧城派和终局逻辑。  
  
必须完成  
  
1. 初始化项目结构。  
2. 建立基础配置读取系统。  
3. 建立核心状态模型：  
    * GameState  
    * CalendarState  
    * PopulationState  
    * ResourceState  
    * FurnaceState  
    * BuildingState  
    * LawState  
    * TechState  
    * EventState  
    * PromiseState  
    * OldCityState  
    * FinalResultState  
4. 建立配置状态枚举：  
    * FINAL  
    * USER_OVERRIDE  
    * TEST_NUMERIC  
    * PENDING  
    * DEPRECATED  
    * TODO_TEXT  
5. 建立 TextRegistry。  
6. 建立 PendingRegistry。  
7. 建立 DeprecatedRegistry 或等效排除机制。  
8. 建立缺失 text_id 检查。  
9. 建立 TODO_TEXT 扫描测试。  
10. 建立基础单元测试框架。  
11. 建立最小启动入口，确认项目可运行。  
12. 建立保存数据版本字段，为后续存档迁移预留接口。  
  
文案规则  
  
所有玩家可见文案通过 text_id 读取。  
  
本轮可只导入少量基础 text_id 作为示例。  
  
未封存正文使用 TODO_TEXT，不得自行创作。  
  
系统内部规则不得进入正式 TextRegistry。  
  
本轮不做  
  
* 不实现完整 end_day。  
* 不实现 build 结算。  
* 不实现科技研究。  
* 不实现炉律签署。  
* 不实现事件触发。  
* 不实现第七霜落。  
* 不实现终局评分。  
* 不实现完整玩家界面。  
* 不批量导入所有文案。  
* 不补任何 PENDING 数值或效果。  
  
验收要求  
  
1. 项目可以启动。  
2. 配置文件可以加载。  
3. 状态模型可以初始化。  
4. TextRegistry 可以按 text_id 返回文案。  
5. 缺失 text_id 会被明确报告。  
6. TODO_TEXT 能被测试发现。  
7. DEPRECATED 内容不会进入正式运行配置。  
8. TEST_NUMERIC 在运行时和测试报告中可被识别。  
9. 所有测试通过。  
10. 输出本 Patch 新增的 text_id、配置字段和文件清单。  
  
完成后停止，不继续 PATCH-002。  
