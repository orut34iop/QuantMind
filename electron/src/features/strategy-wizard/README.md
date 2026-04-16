# strategy-wizard

用途：策略向导模块。

## 说明
- 归属路径：electron\src\features\strategy-wizard
- 股票池选股逻辑已简化为基础财务指标：`market_cap`、`pe`、`pb`。
- 标准话术：市值字段统一口径为“接口返回 `market_cap` 使用元，前端展示统一换算为亿（`/100000000`）；后端通过 `AI_STRATEGY_TOTAL_MV_PER_YI` 适配数据库 `total_mv` 单位（默认按万元）”。
- 快速模板新增并内置：`沪深300`、`中证1000`。
- 快速模板包含 `金融股`，用于触发金融行业选股入口。
- 可视化构建器（SimpleLogicBuilder）在“确认并下一步”时会调用 parse-conditions + query-pool 生成股票池，保证与自然语言入口一致。
- 可视化构建器中 `market_cap` 输入单位固定为“亿”，后端 `parse-conditions` 会统一换算到数据库口径 `total_mv`（默认按万元，可配置覆盖），确保与自然语言入口一致。
- `parse-text` 结果仅在后端返回明确 `mapping.defaults` 时才会回填到可视化构建器，避免使用占位阈值导致条件漂移。
- 策略向导内部统一通过 token 解析用户身份（优先 `sub/user_id`）构造 `user_id`，避免历史数据中不同用户ID格式导致股票池复用/保存查询不一致。
- 已移除复杂条件模块（嵌套逻辑树/高级条件编辑），统一使用简化构建器。
- 第四步 `generate-qlib` 默认超时提升为 `600000ms`（10 分钟），可通过 `VITE_STRATEGY_GENERATE_TIMEOUT_MS` 覆盖，避免大模型长耗时生成被前端提前中断。
- 第四步 `generate-qlib` 已改为“提交异步任务 + 轮询结果”模式：前端调用 `POST /strategy/generate-qlib/async` 后轮询 `GET /strategy/generate-qlib/tasks/{task_id}`，避免网关长连接超时导致 `504`。
- 可通过 `VITE_STRATEGY_GENERATE_POLL_MS` 调整轮询间隔（默认 2000ms）。
- 第四步会将 `position_config`（仓位管理）与 `risk_config + style`（风格/风控）完整提交后端，由后端归一化字段后注入 LLM 提示词。
- 第三步调仓周期已统一为 `1/3/5` 交易日口径（与快速回测一致），并向后兼容旧字段 `rebalance_period`。
- 修改本目录代码后请同步更新本 README
