#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seed_qlib_strategy.py
将一个简单 Qlib 动量策略保存到 user_id=00000001 的云端策略中心。
"""

from backend.shared.strategy_storage import get_strategy_storage_service
from backend.shared.database_pool import get_database_pool, PoolConfig
import asyncio
import os
import sys

# ─────────────────────────── 加载 .env ────────────────────────────
from pathlib import Path

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(str(env_path), override=True)

# 确保项目根在 sys.path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ──────────────────── 手动注册 PostgreSQL 连接 ────────────────────
# 绕过 init_default_databases 的 MySQL 检测逻辑（DATABASE_URL=localhost 导致误判）

PG_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+psycopg2://quantmind:admin123@192.168.1.88:6789/quantmind",
    "postgresql+psycopg2://quantmind:admin123@192.168.1.88:6789/quantmind",
)
pool = get_database_pool()
if "postgres" not in pool._session_factories:
    pool.register_database(
        "postgres", PG_URL, PoolConfig(pool_size=5, max_overflow=2))

# ──────────────────── 获取 StrategyStorageService ─────────────────

# ═════════════════════════════════════════════════════════════════════
# Qlib 动量策略代码（完整、可直接回测）
# ═════════════════════════════════════════════════════════════════════
STRATEGY_CODE = '''"""
策略名称: Qlib 20日动量 + 等权重再平衡
描述    : 基于 qlib 框架的均线动量策略 Demo，每月等权持有过去 20 日收益率排名靠前的 N 支股票
作者    : QuantMind AI
版本    : 1.0.0
回测区间: 2018-01-01 ~ 2023-12-31 (需配合 qlib 数据使用)
"""

import pandas as pd
import numpy as np

try:
    import qlib
    from qlib.config import REG_CN
    from qlib.data import D
    from qlib.contrib.strategy import TopkDropoutStrategy
    from qlib.contrib.evaluate import backtest_daily, risk_analysis
    from qlib.backtest import backtest, executor as exec_module
    from qlib.rl.order_execution import SAOEMetrics
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False


# ─────────────────────────── 配置 ────────────────────────────────

CONFIG = {
    "topk": 30,           # 持仓股票数量
    "drop_n": 5,           # 每次换仓淘汰数量
    "smooth_steps": 5,     # 平滑步数
    "momentum_window": 20, # 动量回望窗口（交易日）
    "start_time": "2018-01-01",
    "end_time":   "2023-12-31",
    "market":     "csi300",
    "benchmark":  "SH000300",  # 沪深300 指数
    "freq":       "day",
    "initial_cash": 1_000_000.0,
}


# ─────────────────────────── 信号计算 ────────────────────────────

def compute_momentum_signal(start: str, end: str, window: int = 20) -> pd.Series:
    """
    用 qlib 数据接口计算动量因子：过去 window 日累计收益率。
    返回多索引 Series: (date, instrument) → momentum_score
    """
    if not QLIB_AVAILABLE:
        raise RuntimeError("qlib 未安装，无法计算动量信号")

    close = D.features(
        D.instruments(CONFIG["market"]),
        ["$close"],
        start_time=start,
        end_time=end,
        freq="day",
    )["$close"]

    momentum = close.groupby(level="instrument").pct_change(periods=window)
    return momentum.dropna()


# ─────────────────────────── 主策略函数 ──────────────────────────

def run_strategy():
    """
    完整回测流程:
      1. 初始化 qlib
      2. 计算动量信号
      3. 调用 TopkDropoutStrategy 进行每日选股
      4. 执行回测并输出年化收益、夏普比等关键指标
    """
    if not QLIB_AVAILABLE:
        print("[WARN] qlib 未安装，跳过回测，仅展示策略逻辑。")
        return _dry_run()

    # 1. 初始化 qlib（需预先下载数据）
    qlib.init(provider_uri="~/.qlib/qlib_data/cn_data", region=REG_CN)

    # 2. 动量信号
    print(f"[INFO] 计算 {CONFIG['momentum_window']} 日动量信号...")
    signal = compute_momentum_signal(
        CONFIG["start_time"], CONFIG["end_time"], CONFIG["momentum_window"]
    )
    # 转为每日截面 score DataFrame，符合 TopkDropoutStrategy 输入格式
    pred = signal.unstack(level="instrument")

    # 3. 构造策略
    strategy = TopkDropoutStrategy(
        signal=pred,
        topk=CONFIG["topk"],
        n_drop=CONFIG["drop_n"],
    )

    # 4. 执行回测
    executor_config = {
        "class": "SimulatorExecutor",
        "module_path": "qlib.backtest.executor",
        "kwargs": {
            "time_per_step": "day",
            "generate_portfolio_metrics": True,
            "verbose": False,
        },
    }
    portfolio_metric_dict, indicator_dict = backtest(
        start_time=CONFIG["start_time"],
        end_time=CONFIG["end_time"],
        strategy=strategy,
        executor=executor_config,
        account=CONFIG["initial_cash"],
        benchmark=CONFIG["benchmark"],
        exchange_kwargs={
            "freq": CONFIG["freq"],
            "limit_threshold": 0.095,
            "deal_price": "close",
            "open_cost": 0.0005,
            "close_cost": 0.0015,
            "min_n_cost": 5,
        },
    )

    # 5. 风险分析
    analysis = risk_analysis(portfolio_metric_dict["1day"]["return"])
    print("\n[RESULT] 策略回测结果 (1day)")
    print(analysis)
    return analysis


def _dry_run():
    """qlib 不可用时的模拟运行，用于验证代码逻辑。"""
    print("[DRY-RUN] 动量策略 dry-run 完成，参数:")
    for k, v in CONFIG.items():
        print(f"  {k}: {v}")
    result = {
        "annualized_return": "N/A (dry-run)",
        "sharpe_ratio": "N/A (dry-run)",
        "max_drawdown": "N/A (dry-run)",
    }
    return result


# ─────────────────────────── 入口 ────────────────────────────────

if __name__ == "__main__":
    run_strategy()
'''


async def main():
    svc = get_strategy_storage_service()

    print("=" * 60)
    print("正在保存 Qlib 动量策略到云端策略中心...")
    print("  目标用户: user_id=00000001 (DB id=1)")
    print(f"  COS 模式: {'local' if svc._local_mode else 'COS (腾讯云)'}")
    print("=" * 60)

    result = await svc.save(
        user_id="00000001",  # 业务用户 ID
        name="Qlib 20日动量策略",
        code=STRATEGY_CODE,
        metadata={
            "description": (
                "基于 qlib 框架的均线动量 Demo 策略。"
                "每月等权持有过去 20 日收益率排名靠前的 N 支沪深300成分股。"
                "含完整可运行的回测代码，支持 TopkDropoutStrategy。"
            ),
            "tags": ["qlib", "动量", "A股", "demo", "AI生成"],
            "strategy_type": "QUANTITATIVE",  # PG 枚举值：大写
            "status": "ACTIVE",  # PG 枚举值：大写
            "is_public": False,
            "parameters": {
                "topk": 30,
                "drop_n": 5,
                "momentum_window": 20,
                "start_time": "2018-01-01",
                "end_time": "2023-12-31",
                "market": "csi300",
            },
        },
    )

    print("\n✅ 保存成功！")
    print(f"  strategy_id : {result['id']}")
    print(f"  cos_key     : {result['cos_key']}")
    print(f"  code_hash   : {result['code_hash']}")
    print(f"  file_size   : {result['file_size']} bytes")
    if result.get("cos_url"):
        url = result["cos_url"]
        print(f"  cos_url     : {url[:80]}{'...' if len(url) > 80 else ''}")
    else:
        print("  cos_url     : (local mode，无预签名 URL)")

    # 验证：通过列表接口读回
    print("\n🔍 验证：列出 user_id=00000001 的所有策略...")
    strategies = svc.list(user_id="00000001")
    print(f"  共 {len(strategies)} 条策略")
    for s in strategies[:5]:
        print(
            f"  - [{s['id']}] {s['name']} | tags={s['tags']} | status={s['status']}")

    return result


if __name__ == "__main__":
    # 提取 CONFIG 到模块级别供 metadata 使用
    CONFIG = {
        "topk": 30,
        "drop_n": 5,
        "smooth_steps": 5,
        "momentum_window": 20,
        "start_time": "2018-01-01",
        "end_time": "2023-12-31",
        "market": "csi300",
        "benchmark": "SH000300",
        "freq": "day",
        "initial_cash": 1_000_000.0,
    }
    asyncio.run(main())
