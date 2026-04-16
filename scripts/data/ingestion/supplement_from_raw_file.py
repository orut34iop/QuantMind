import asyncio
import os
import logging
import pandas as pd
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

DATA_FILE = r"E:\code\quantmind\db\相对价值指标144226681\FI_T10.csv"


async def supplement_pe_ps_from_raw():
    logger.info("Starting PE/PS/PB supplementation from FI_T10.csv...")

    # Read CSV file
    logger.info("Loading CSV file...")
    df = pd.read_csv(DATA_FILE, encoding="utf-8")
    logger.info(f"Loaded {len(df)} records")

    # Convert date and sort to get latest data
    df["Accper"] = pd.to_datetime(df["Accper"])
    df = df.sort_values(["Stkcd", "Accper"], ascending=[True, False])

    # Get latest record for each stock
    latest_df = df.groupby("Stkcd").first().reset_index()
    logger.info(f"Found latest data for {len(latest_df)} stocks")

    # Prepare data for update
    # Use PE TTM, PS TTM, and PB
    update_data = []
    for _, row in latest_df.iterrows():
        symbol = str(row["Stkcd"]).zfill(6)  # Ensure 6-digit format

        # Get PE TTM (F100103C), PS TTM (F100203C), PB (F100401A)
        pe_ttm = row.get("F100103C")
        ps_ttm = row.get("F100203C")
        pb = row.get("F100401A")

        # Convert to float, handle NaN
        pe = float(pe_ttm) if pd.notna(pe_ttm) else None
        ps = float(ps_ttm) if pd.notna(ps_ttm) else None
        pb_val = float(pb) if pd.notna(pb) else None

        update_data.append((symbol, pe, ps, pb_val))

    logger.info(f"Prepared {len(update_data)} records for update")

    # Connect to PostgreSQL
    pg_conn = await asyncpg.connect(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT
    )
    logger.info("Connected to PostgreSQL")

    # Batch update
    chunk_size = 1000
    total_updated = 0

    for i in range(0, len(update_data), chunk_size):
        chunk = update_data[i: i + chunk_size]

        await pg_conn.executemany(
            """
            UPDATE stock_selection
            SET
                pe_ratio = COALESCE(pe_ratio, $2),
                ps_ratio = COALESCE(ps_ratio, $3),
                pb_ratio = COALESCE(pb_ratio, $4)
            WHERE symbol = $1
        """,
            chunk,
        )

        total_updated += len(chunk)
        if total_updated % 1000 == 0:
            logger.info(
                f"Processed {total_updated}/{len(update_data)} stocks...")

    await pg_conn.close()
    logger.info(
        f"PE/PS/PB supplementation completed! Updated {total_updated} stocks.")



if __name__ == "__main__":
    asyncio.run(supplement_pe_ps_from_raw())
