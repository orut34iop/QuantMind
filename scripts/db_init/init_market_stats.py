import os
import pandas as pd
import baostock as bs
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# 数据库连接配置，优先使用统一的 DATABASE_URL，其次使用 DB_* 环境变量
def get_db_url() -> str:
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


# 实际使用的 DB URL
DB_URL = get_db_url()


def init_stats_table():
    """创建市场每日统计表"""
    engine = create_engine(DB_URL)
    sql = """
    CREATE TABLE IF NOT EXISTS market_daily_stats (
        trade_date DATE PRIMARY KEY,
        sh_amount FLOAT, -- 上证成交额 (元)
        sz_amount FLOAT, -- 深证成交额 (元)
        total_amount FLOAT, -- 两市总成交额 (元)
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_mds_date ON market_daily_stats(trade_date DESC);
    """
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print("✅ market_daily_stats 表结构初始化完成")


def get_index_data(code, start_date, end_date):
    """从 BaoStock 获取指数成交额数据"""
    rs = bs.query_history_k_data_plus(
        code, "date,amount", start_date=start_date, end_date=end_date, frequency="d"
    )
    data_list = []
    while (rs.error_code == "0") & rs.next():
        data_list.append(rs.get_row_data())

    df = pd.DataFrame(data_list, columns=rs.fields)
    df = df.rename(columns={"date": "trade_date", "amount": "amount"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["amount"] = df["amount"].astype(float)
    return df


def sync_historical_stats():
    """使用 BaoStock 同步近半年的两市成交额数据"""
    print("正在通过 BaoStock 获取近半年两市历史数据...")

    # 登录系统
    lg = bs.login()
    if lg.error_code != "0":
        print(f"❌ BaoStock 登录失败: {lg.error_msg}")
        return

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
<<<<<<< HEAD
        start_date = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")
=======
        start_date = (datetime.now() - timedelta(days=250)
                      ).strftime("%Y-%m-%d")
>>>>>>> refactor/service-cleanup

        # 上证指数 (sh.000001)
        sh_df = get_index_data("sh.000001", start_date, end_date)
        # 深证成指 (sz.399001)
        sz_df = get_index_data("sz.399001", start_date, end_date)

        # 合并数据
<<<<<<< HEAD
        merged_df = pd.merge(sh_df, sz_df, on="trade_date", suffixes=("_sh", "_sz"))

        # 计算总成交额
        merged_df["total_amount"] = merged_df["amount_sh"] + merged_df["amount_sz"]

        # 准备入库数据
        final_df = merged_df[["trade_date", "amount_sh", "amount_sz", "total_amount"]]
=======
        merged_df = pd.merge(sh_df, sz_df, on="trade_date",
                             suffixes=("_sh", "_sz"))

        # 计算总成交额
        merged_df["total_amount"] = merged_df["amount_sh"] + \
            merged_df["amount_sz"]

        # 准备入库数据
        final_df = merged_df[["trade_date",
                              "amount_sh", "amount_sz", "total_amount"]]
>>>>>>> refactor/service-cleanup
        final_df = final_df.rename(
            columns={"amount_sh": "sh_amount", "amount_sz": "sz_amount"}
        )

        # 写入数据库
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            # 使用 temp table 处理 ON CONFLICT
            final_df.to_sql(
                "market_daily_stats_temp", engine, if_exists="replace", index=False
            )
            conn.execute(text("""
                INSERT INTO market_daily_stats (trade_date, sh_amount, sz_amount, total_amount)
                SELECT trade_date, sh_amount, sz_amount, total_amount FROM market_daily_stats_temp
                ON CONFLICT (trade_date) DO UPDATE SET
                    sh_amount = EXCLUDED.sh_amount,
                    sz_amount = EXCLUDED.sz_amount,
                    total_amount = EXCLUDED.total_amount;
                DROP TABLE market_daily_stats_temp;
            """))
            conn.commit()

        print(f"✅ 成功同步 {len(final_df)} 条市场统计数据 (BaoStock)")
        if not final_df.empty:
            print(f"   最新交易日: {final_df['trade_date'].iloc[-1]}")
            print(
                f"   最新两市总成交额: {final_df['total_amount'].iloc[-1] / 1e8:.2f} 亿元"
            )

    except Exception as e:
        print(f"❌ 数据同步失败: {e}")
    finally:
        # 登出系统
        bs.logout()


if __name__ == "__main__":
    init_stats_table()
    sync_historical_stats()
