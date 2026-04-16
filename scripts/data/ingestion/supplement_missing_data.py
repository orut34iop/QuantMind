from data_sources.ths_api import get_ths_api
import os
import sys
import logging
import asyncio
import pandas as pd
import asyncpg
from datetime import datetime
from dotenv import load_dotenv
from typing import List

# Ensure project root is in path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

DB_HOST = (os.getenv("DB_MASTER_HOST") or "127.0.0.1").strip()
DB_PORT = (os.getenv("DB_MASTER_PORT") or "5432").strip()
DB_USER = (os.getenv("DB_USER") or "quantmind").strip()
DB_PASSWORD = (os.getenv("DB_PASSWORD") or "admin123").strip()
DB_NAME = (os.getenv("DB_NAME") or "quantmind").strip()


async def get_symbols_with_missing_data(conn) -> List[str]:
    """获取存在缺失数据的股票代码列表"""
    rows = await conn.fetch("""
        SELECT DISTINCT symbol
        FROM stock_selection
        WHERE pe_ratio IS NULL
           OR pb_ratio IS NULL
           OR ps_ratio IS NULL
           OR roe IS NULL
    """)
    return [row["symbol"] for row in rows]


async def supplement_valuation_data(conn, symbol: str, ths_api):
    """补全估值数据 (PE, PB, PS)"""
    logger.info(f"Fetching valuation data for {symbol}...")
    df = ths_api.get_valuation_data(symbol)
    if df is None or df.empty:
        return

    # Standardize columns (Legu specific)
    # trade_date, pe, pb, ps
    # Note: legu columns are often 'trade_date', 'pe', 'pb', 'ps'

    # Batch update
    update_count = 0
    total_in_api = len(df)
    for i, row in df.iterrows():
        try:
            trade_date = row["trade_date"]
            # Debug sample
            if i == 0:
                logger.info(
                    f"Sample API date: {trade_date} (type: {type(trade_date)})")

            # Convert to date if it's timestamp or string
            if isinstance(trade_date, str):
                trade_date = datetime.strptime(trade_date, "%Y-%m-%d").date()
            elif hasattr(trade_date, "date"):
                trade_date = trade_date.date()

            res = await conn.execute(
                """
                UPDATE stock_selection
                SET pe_ratio = $1, pb_ratio = $2, ps_ratio = $3
                WHERE symbol = $4 AND trade_date = $5
            """,
                float(row.get("pe")) if row.get("pe") else None,
                float(row.get("pb")) if row.get("pb") else None,
                float(row.get("ps")) if row.get("ps") else None,
                symbol,
                trade_date,
            )

            if "UPDATE 1" in res:
                update_count += 1
        except Exception as e:
            if i == 0:
                logger.error(f"Update error for {symbol}: {e}")
            continue
    logger.info(
        f"Updated {update_count}/{total_in_api} valuation records for {symbol}")



async def supplement_financial_data(conn, symbol: str, ths_api):
    """补全财务数据 (ROE)"""
    logger.info(f"Fetching financial data for {symbol}...")
    df = ths_api.get_financial_data(symbol)
    if df is None or df.empty:
        return

    # ROE typically comes from quarterly reports. we need to propagate it to daily records.
    # We use the ROE of the latest report for the subsequent trading days until the next report.

    # Sort by date (ascending)
    df["报告期"] = pd.to_datetime(df["报告期"])
    df = df.sort_values("报告期", ascending=True)

    # Mapping '净资产收益率(%)' to roe
    roe_col = "净资产收益率(%)"
    if roe_col not in df.columns:
        for c in df.columns:
            if "净资产收益率" in c:
                roe_col = c
                break

    if roe_col not in df.columns:
        logger.warning(f"ROE column not found for {symbol}")
        return

    # Use only the LATEST report for efficiency, as our db records are for 2026-01
    latest_row = df.iloc[-1]
    report_date = latest_row["报告期"].date()
    roe_val = latest_row[roe_col]

    try:
        # Handle string percentage format like "9.76%"
        if isinstance(roe_val, str):
            roe_val = roe_val.strip().rstrip("%")
        roe_val = float(
            roe_val) if roe_val is not None and roe_val != "" else None
    except (ValueError, TypeError):
        logger.warning(f"Failed to convert ROE for {symbol}: {roe_val}")
        roe_val = None

    if roe_val is not None:
        # Convert % to decimal (if value was already in percentage form)
        if roe_val > 1.0 or roe_val < -1.0:
            roe_val = roe_val / 100.0

        res = await conn.execute(
            """
            UPDATE stock_selection
            SET roe = $1
            WHERE symbol = $2 AND roe IS NULL
        """,
            roe_val,
            symbol,
        )
        logger.info(
            f"ROE Optimized Update for {symbol}: {res} (Using latest report: {report_date}, ROE: {roe_val:.4f})"
        )


async def main():
    logger.info("Starting ROE data supplementation from THS (60 stocks/sec)...")
    conn = await asyncpg.connect(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT
    )

    ths_api = get_ths_api()
    # Focus on symbols missing ROE
    rows = await conn.fetch(
        "SELECT DISTINCT symbol FROM stock_selection WHERE roe IS NULL"
    )
    symbols = [row["symbol"] for row in rows]
    logger.info(f"Found {len(symbols)} symbols missing ROE")

    processed = 0
    for symbol in symbols:
        try:
            await supplement_financial_data(conn, symbol, ths_api)
            processed += 1

            # Progress logging every 100 stocks
            if processed % 100 == 0:
                logger.info(
                    f"Progress: {processed}/{len(symbols)} stocks processed")

            # Sleep to respect rate limit: 60 stocks/sec = ~0.017s per stock
            await asyncio.sleep(0.017)
        except Exception as e:
            logger.error(f"Failed to process {symbol}: {e}")

    await conn.close()
    logger.info(
        f"ROE supplementation completed! Processed {processed} stocks.")



if __name__ == "__main__":
    asyncio.run(main())
