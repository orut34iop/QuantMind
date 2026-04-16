# QuantMind 数据库精简说明

## 概述

开源版数据库从 **75 张表** 精简至 **22 张表**，移除了企业级功能相关表。

## 保留表清单 (22张)

### 用户与认证 (4张)
| 表名 | 说明 |
|-----|------|
| `users` | 用户主表 |
| `user_profiles` | 用户资料 |
| `user_sessions` | 会话管理 |
| `api_keys` | API密钥 |

### 策略管理 (3张)
| 表名 | 说明 |
|-----|------|
| `strategies` | 策略表 |
| `user_strategies` | 用户策略 |
| `stock_pool_files` | 股票池文件 |

### 回测引擎 (2张)
| 表名 | 说明 |
|-----|------|
| `qlib_backtest_runs` | 回测记录 |
| `qlib_optimization_runs` | 参数优化 |

### 模拟交易 (5张)
| 表名 | 说明 |
|-----|------|
| `simulation_jobs` | 模拟任务 |
| `sim_orders` | 模拟订单 |
| `sim_trades` | 模拟成交 |
| `simulation_positions` | 模拟持仓 |
| `simulation_fund_snapshots` | 资金快照 |

### 行情数据 (3张)
| 表名 | 说明 |
|-----|------|
| `stocks` | 股票基础信息 |
| `market_data_daily` | 日线数据(含48维特征) |
| `stock_daily_latest` | 最新日线 |

### 模型推理 (2张)
| 表名 | 说明 |
|-----|------|
| `qm_user_models` | 用户模型 |
| `qm_model_inference_runs` | 推理记录 |

### 系统管理 (3张)
| 表名 | 说明 |
|-----|------|
| `notifications` | 通知 |
| `system_settings` | 系统配置 |
| `audit_logs` | 审计日志 |

## 删除表清单 (53张)

### 支付与订阅 (4张) ❌
- `payment_methods` - 支付方式
- `payment_transactions` - 支付交易
- `subscription_plans` - 订阅计划
- `user_subscriptions` - 用户订阅

### 实盘交易 (5张) ❌
- `real_account_snapshots` - 实盘快照
- `real_account_ledger_daily_snapshots` - 日账本
- `real_account_baselines` - 账户基线
- `real_trading_preflight_snapshots` - 预检快照
- `trade_manual_execution_tasks` - 手动执行任务

### QMT代理 (2张) ❌
- `qmt_agent_bindings` - QMT绑定
- `qmt_agent_sessions` - QMT会话

### KYC验证 (3张) ❌
- `identity_verifications` - 身份验证
- `email_verifications` - 邮箱验证
- `phone_verifications` - 手机验证

### 权限系统 (5张) ❌
- `roles` - 角色
- `permissions` - 权限
- `user_roles` - 用户角色
- `role_permissions` - 角色权限
- `risk_rules` - 风控规则

### 社区功能 (5张) ❌
- `community_posts` - 社区帖子
- `community_comments` - 社区评论
- `community_interactions` - 社区互动
- `community_author_follows` - 作者关注
- `community_audit_logs` - 社区审计

### 管理后台 (3张) ❌
- `admin_data_files` - 数据文件
- `admin_models` - 管理模型
- `admin_training_jobs` - 训练任务

### 高级行情 (4张) ❌
- `quotes` - 实时行情
- `klines` - K线数据
- `quote_daily_summaries` - 日行情汇总
- `market_daily_stats` - 市场统计

### 特征工程 (8张) ❌
- `qm_feature_category` - 特征分类
- `qm_feature_definition` - 特征定义
- `qm_feature_set_item` - 特征集项
- `qm_feature_set_version` - 特征集版本
- `engine_feature_runs` - 特征运行
- `engine_feature_snapshots` - 特征快照
- `engine_signal_scores` - 信号分数
- `engine_dispatch_batches` - 调度批次
- `engine_dispatch_items` - 调度项

### 交易日历 (4张) ❌
- `qm_market_calendar_day` - 日历日
- `qm_market_calendar_exception` - 日历异常
- `qm_market_calendar_version` - 日历版本
- `qm_market_trading_session` - 交易时段

### 其他 (10张) ❌
- `login_devices` - 登录设备
- `password_reset_tokens` - 密码重置
- `industry_classification` - 行业分类
- `backtests` - 旧回测表
- `orders` / `trades` - 实盘订单/成交
- `positions` / `position_history` - 实盘持仓
- `portfolios` / `portfolio_snapshots` - 组合
- `pipeline_runs` - Pipeline运行
- `strategy_loop_tasks` - 策略循环任务
- `system_tasks` - 系统任务
- `simulation_daily_reports` - 模拟日报
- `user_audit_logs` - 用户审计
- `alembic_version` / `alembic_version_community` - 迁移版本
- `qlib_backtest_runs_cleanup_backup` - 备份表

## 初始化数据

### 默认管理员
- 用户名: `admin`
- 邮箱: `admin@quantmind.local`
- 密码: 需通过API重置

### 系统配置
- `storage_mode`: local
- `backtest.default_initial_capital`: 100000000
- `backtest.default_benchmark`: SH000300

## 使用方式

```bash
# 创建数据库
psql -U postgres -c "CREATE DATABASE quantmind OWNER quantmind;"

# 导入初始化SQL
psql -U quantmind -d quantmind -f data/quantmind_init.sql
```
