import asyncio
import os
import logging
import duckdb
import asyncpg
from dotenv import load_dotenv

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

DUCKDB_PATH = "E:/code/quantmind/db/stock_new.duckdb"


async def supplement_pe_pb_simple():
    logger.info("Starting PE/PB supplementation from DuckDB...")

    # Connect to DuckDB and get data as list of tuples
    duck_conn = duckdb.connect(DUCKDB_PATH, read_only=True)
    logger.info("Connected to DuckDB")

    # Fetch data directly as tuples (much faster than pandas)
    rows = duck_conn.execute("""
        SELECT
            LPAD(CAST(stock_code AS VARCHAR), 6, '0') as symbol,
            CAST(pe_ratio_ttm AS DOUBLE) as pe_ratio,
            CAST(pb_ratio AS DOUBLE) as pb_ratio
        FROM fi_raw
        WHERE pe_ratio_ttm IS NOT NULL OR pb_ratio IS NOT NULL
    """).fetchall()

    logger.info(f"Fetched {len(rows)} records from DuckDB")
    duck_conn.close()

    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT
    )
    logger.info("Connected to PostgreSQL")

    # Batch update in chunks
    chunk_size = 1000
    total_updated = 0

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i: i + chunk_size]

        # Use executemany for batch updates
        await pg_conn.executemany(
            """
            UPDATE stock_selection
            SET
                pe_ratio = COALESCE(pe_ratio, $2),
                pb_ratio = COALESCE(pe_ratio, $3)
            WHERE symbol = $1
        """,
            chunk,
        )

        total_updated += len(chunk)
        if total_updated % 5000 == 0:
            logger.info(f"Processed {total_updated}/{len(rows)} records...")

    await pg_conn.close()
    logger.info(
        f"PE/PB supplementation completed! Processed {total_updated} records.")



if __name__ == "__main__":
    asyncio.run(supplement_pe_pb_simple())
