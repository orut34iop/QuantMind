import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = (os.getenv("DB_MASTER_HOST") or "127.0.0.1").strip()
DB_PORT = (os.getenv("DB_MASTER_PORT") or "5432").strip()
DB_USER = (os.getenv("DB_USER") or "quantmind").strip()
DB_PASSWORD = (os.getenv("DB_PASSWORD") or "admin123").strip()
DB_NAME = (os.getenv("DB_NAME") or "quantmind").strip()


async def verify():
    print(f"Connecting to {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}...")
    conn = await asyncpg.connect(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT
    )

    # 1. 统计总数
    count = await conn.fetchval("SELECT count(*) FROM stock_selection")
    print(f"\n[1] Total records in PostgreSQL: {count}")

    # 2. 检查日期覆盖范围
    dates = await conn.fetch(
        "SELECT min(trade_date) as start, max(trade_date) as end FROM stock_selection"
    )
    print(f"[2] Date Range: {dates[0]['start']} to {dates[0]['end']}")

    # 3. 检查指标填充率 (以 MACD 和 RSI 为例)
    null_check = await conn.fetch("""
        SELECT
            count(*) filter (where macd_dif is null) as null_macd,
            count(*) filter (where rsi is null) as null_rsi,
            count(*) filter (where industry is null) as null_industry
        FROM stock_selection
    """)
    print("[3] Data Completeness (NULL counts):")
    print(f"    - MACD_DIF NULLs: {null_check[0]['null_macd']}")
    print(f"    - RSI NULLs: {null_check[0]['null_rsi']}")
    print(f"    - Industry NULLs: {null_check[0]['null_industry']}")

    # 4. 抽取样本展示
    samples = await conn.fetch("""
        SELECT symbol, name, trade_date, close, macd_dif, kdj_k, rsi, industry, is_st
        FROM stock_selection
        WHERE macd_dif IS NOT NULL
        LIMIT 3
    """)
    print("\n[4] Data Samples:")
    for row in samples:
        print(
            f"    Stock: {row['symbol']} ({row['name']}) | Date: {row['trade_date']}")
        print(
            f"    Close: {row['close']} | MACD_DIF: {row['macd_dif']:.4f} | RSI: {row['rsi']:.2f}"
        )
        print(f"    Industry: {row['industry']} | IS_ST: {row['is_st']}")
        print("-" * 50)

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
