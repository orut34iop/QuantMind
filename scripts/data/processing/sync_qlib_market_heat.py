import os
import sys
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from pathlib import Path

# 添加项目路径
sys.path.append(os.getcwd())

# 配置 - 优先使用统一的 DATABASE_URL
def get_db_url():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST")
    port = os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    db = os.getenv("DB_NAME")
    missing = [k for k, v in (("DB_HOST", host), ("DB_PORT", port), ("DB_USER", user), ("DB_PASSWORD", password), ("DB_NAME", db)) if not v]
    if missing:
        raise RuntimeError(f"Missing DB env vars: {', '.join(missing)}. Please set DATABASE_URL or DB_* in root .env")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


DB_URL = get_db_url()
QLIB_DATA_DIR = Path("db/qlib_data")  # 统一使用 qlib_data 作为 Qlib 数据目录


def sync_heat_to_qlib():
    """将市场热度数据同步为 Qlib 全局特征"""
    print("🚀 开始将市场热度同步至 Qlib 数据集...")

    engine = create_engine(DB_URL)
    try:
        # 1. 从数据库读取全量历史统计
        query = "SELECT trade_date, total_amount FROM market_daily_stats ORDER BY trade_date ASC"
        df = pd.read_sql(query, engine)

        if len(df) < 120:
            print("❌ 错误: 数据库中历史数据不足 120 天，无法计算有效热度。")
            return

        # 2. 计算每日热度比率 (滚动计算)
        df['short_avg'] = df['total_amount'].rolling(window=5).mean()
        df['long_avg'] = df['total_amount'].rolling(window=120).mean()
        df['market_heat'] = (df['short_avg'] / df['long_avg']).fillna(1.0)

        # 限制范围 0.3 - 1.0
        df['market_heat'] = df['market_heat'].clip(0.3, 1.0)

        # 3. 转化为 Qlib 格式 (每股都需要看到这个全局因子)
        # 方案：Qlib 的全局特征通常存放在特殊的 instruments 或者通过 expression 直接计算。
        # 这里我们将热度数据导出为一个 CSV，以便 Qlib 离线任务或 DataHandler 挂载。

        output_path = QLIB_DATA_DIR / "market_intelligence"
        output_path.mkdir(parents=True, exist_ok=True)

        heat_file = output_path / "global_heat.csv"
        df[['trade_date', 'market_heat']].to_csv(heat_file, index=False)

        print(f"✅ 成功生成热度历史特征: {heat_file}")
        print(
            f"   覆盖日期范围: {df['trade_date'].iloc[0]} 至 {df['trade_date'].iloc[-1]}")
        print(f"   最新热度值: {df['market_heat'].iloc[-1]:.4f}")

        # 4. 指导说明
        print("\n[开发提示]")
        print("Qlib 策略现在可以通过以下伪代码访问此因子:")
        print("   heat_df = pd.read_csv('global_heat.csv')")
        print(
            "   current_heat = heat_df[heat_df['trade_date'] == current_date]['market_heat']")

    except Exception as e:
        print(f"❌ 同步失败: {e}")


if __name__ == "__main__":
    sync_heat_to_qlib()
