from data_sources.ths_api import get_ths_api
import os
import sys
import logging
import asyncio
import pandas as pd
import asyncpg
from dotenv import load_dotenv

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

# Concurrent processing settings
MAX_CONCURRENT = 60  # Process 60 stocks concurrently
BATCH_SIZE = 100  # Log progress every 100 stocks


async def supplement_financial_data_concurrent(pool, symbol: str, ths_api, semaphore):
    """补全财务数据 (ROE) with concurrency control"""
    async with semaphore:
        try:
            logger.debug(f"Fetching financial data for {symbol}...")
            df = ths_api.get_financial_data(symbol)
            if df is None or df.empty:
                return False

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
                return False

            # Use only the LATEST report for efficiency
            latest_row = df.iloc[-1]
            report_date = latest_row["报告期"].date()
            roe_val = latest_row[roe_col]

            try:
                # Handle string percentage format like "9.76%"
                if isinstance(roe_val, str):
                    roe_val = roe_val.strip().rstrip("%")
                roe_val = (
                    float(roe_val) if roe_val is not None and roe_val != "" else None
                )
            except (ValueError, TypeError):
                logger.warning(
                    f"Failed to convert ROE for {symbol}: {roe_val}")
                return False

            if roe_val is not None:
                # Convert % to decimal (if value was already in percentage form)
                if roe_val > 1.0 or roe_val < -1.0:
                    roe_val = roe_val / 100.0

                # Get connection from pool for this operation
                async with pool.acquire() as conn:
                    res = await conn.execute(
                        """
                        UPDATE stock_selection
                        SET roe = $1
                        WHERE symbol = $2 AND roe IS NULL
                    """,
                        roe_val,
                        symbol,
                    )

                    logger.debug(
                        f"ROE Update for {symbol}: {res} (Report: {report_date}, ROE: {roe_val:.4f})"
                    )
                return True
            return False
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return False


async def main():
    logger.info(
        f"Starting ROE data supplementation with {MAX_CONCURRENT} concurrent workers..."
    )

    # Create connection pool instead of single connection
    pool = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
        min_size=10,
        max_size=MAX_CONCURRENT + 10,
    )

    ths_api = get_ths_api()

    # Get symbols missing ROE
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT symbol FROM stock_selection WHERE roe IS NULL"
        )
    symbols = [row["symbol"] for row in rows]
    logger.info(f"Found {len(symbols)} symbols missing ROE")

    # Create semaphore to limit concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    # Process in batches for progress tracking
    total_processed = 0
    total_success = 0

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i: i + BATCH_SIZE]

        # Process batch concurrently
        tasks = [
            supplement_financial_data_concurrent(
                pool, symbol, ths_api, semaphore)
            for symbol in batch
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        batch_success = sum(1 for r in results if r is True)
        total_success += batch_success
        total_processed += len(batch)

        logger.info(
            f"Progress: {total_processed}/{len(symbols)} stocks processed ({total_success} successful)"
        )

    await pool.close()
    logger.info(
        f"ROE supplementation completed! Processed {total_processed} stocks, {total_success} successful updates."
    )


if __name__ == "__main__":
    asyncio.run(main())
