"""
插入演示策略到数据库
用法: python scripts/insert_demo_strategy.py
"""

<<<<<<< HEAD
=======
import psycopg2
>>>>>>> refactor/service-cleanup
import os
import sys
import uuid
from datetime import datetime, timezone

# 加载 .env
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


DB_HOST = os.environ.get("DB_MASTER_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_MASTER_PORT", 5432))
DB_USER = os.environ.get("DB_USER", "quantmind")
DB_PASS = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "quantmind")

DEMO_CODE = '''import pandas as pd
import numpy as np


class DualMAStrategy:
    """
    双均线趋势跟踪策略（演示）
    - 短期均线(5日)上穿长期均线(20日) -> 买入信号
    - 短期均线(5日)下穿长期均线(20日) -> 卖出信号
    """

    def __init__(self, short_window=5, long_window=20):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, prices: pd.Series) -> pd.Series:
        signals = pd.Series(0, index=prices.index)
        short_ma = prices.rolling(self.short_window).mean()
        long_ma = prices.rolling(self.long_window).mean()
        signals[short_ma > long_ma] = 1
        signals[short_ma <= long_ma] = 0
        return signals.diff().fillna(0)  # 1=买入, -1=卖出

    def backtest(self, prices: pd.Series, initial_capital: float = 100_000):
        signals = self.generate_signals(prices)
        returns = prices.pct_change()
        strategy_returns = signals.shift(1) * returns
        cumulative = (1 + strategy_returns).cumprod()
        sharpe = (
            strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
            if strategy_returns.std() > 0 else 0.0
        )
        return {
            "total_return": float(cumulative.iloc[-1] - 1),
            "sharpe_ratio": float(sharpe),
            "max_drawdown": float((cumulative / cumulative.cummax() - 1).min()),
        }
'''


def main():
    print(f"连接数据库 {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} ...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME,
            connect_timeout=5,
        )
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        sys.exit(1)

    cur = conn.cursor()

    # 查看 strategies 表结构
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'strategies'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    if not cols:
        print("❌ strategies 表不存在，尝试列出所有表：")
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public';")
        print([r[0] for r in cur.fetchall()])
        conn.close()
        sys.exit(1)

    print("strategies 表结构:")
    col_names = [c[0] for c in cols]
    for c in cols:
        print(f"  {c[0]:30s} {c[1]}")

    # 获取 admin 的 user_id
    cur.execute("SELECT id, username FROM users WHERE username='admin' LIMIT 1;")
    user = cur.fetchone()
    if not user:
        print("❌ 未找到 admin 用户")
        conn.close()
        sys.exit(1)
    user_id = user[0]
    print(f"\nadmin user_id = {user_id}")

    now = datetime.now(timezone.utc)
    strategy_id = str(uuid.uuid4())

    # 根据实际列名构建插入语句
    demo_strategies = [
        {
            "name": "双均线趋势跟踪策略",
            "description": "基于5日和20日均线的经典趋势跟踪策略，金叉买入死叉卖出",
            "code": DEMO_CODE,
            "tags": ["均线", "趋势跟踪", "经典策略"],
        },
        {
            "name": "RSI超买超卖策略",
            "description": "利用RSI指标识别超买超卖区域，RSI<30买入，RSI>70卖出",
            "code": "# RSI策略示例\n# RSI < 30 -> 买入\n# RSI > 70 -> 卖出\nprint('RSI策略加载成功')\n",
            "tags": ["RSI", "震荡策略", "技术指标"],
        },
    ]

    inserted = 0
    for s in demo_strategies:
        try:
            # 尝试通用插入（根据表结构动态适配）
            if "user_id" in col_names and "code" in col_names:
                cur.execute(
                    """
                    INSERT INTO strategies (id, user_id, name, description, code, tags, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id;
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        s["name"],
                        s["description"],
                        s["code"],
                        s["tags"],
                        "draft",
                        now,
                        now,
                    ),
                )
            elif "user_id" in col_names:
                cur.execute(
                    """
                    INSERT INTO strategies (id, user_id, name, description, tags, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id;
                """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        s["name"],
                        s["description"],
                        s["tags"],
                        "draft",
                        now,
                        now,
                    ),
                )
            else:
                print(f"⚠️  无法确定插入方式，列名: {col_names}")
                break

            result = cur.fetchone()
            if result:
                print(f"✅ 已插入策略: {s['name']} (id={result[0]})")
                inserted += 1
            else:
                print(f"⚠️  策略已存在或冲突: {s['name']}")
        except Exception as e:
            print(f"❌ 插入失败 [{s['name']}]: {e}")
            conn.rollback()
            # 打印实际列名供调试
            print(f"   实际列名: {col_names}")
            conn.close()
            sys.exit(1)

    conn.commit()
    print(f"\n✅ 共插入 {inserted} 条演示策略")

    # 验证
    cur.execute(
<<<<<<< HEAD
        "SELECT id, name, status FROM strategies WHERE user_id = %s;", (user_id,)
=======
        "SELECT id, name, status FROM strategies WHERE user_id = %s;", (
            user_id,)
>>>>>>> refactor/service-cleanup
    )
    rows = cur.fetchall()
    print(f"\n当前 admin 用户的策略列表（共 {len(rows)} 条）:")
    for r in rows:
        print(f"  id={r[0]}  name={r[1]}  status={r[2]}")

    conn.close()


if __name__ == "__main__":
    main()
