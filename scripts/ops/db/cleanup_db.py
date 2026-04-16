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


async def cleanup():
    print(
        f"Connecting to {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME} to cleanup...")
    conn = await asyncpg.connect(
        user=DB_USER, password=DB_PASSWORD, database=DB_NAME, host=DB_HOST, port=DB_PORT
    )

    result = await conn.execute(
        "DELETE FROM stock_selection WHERE trade_date < CURRENT_DATE - INTERVAL '30 days'"
    )
    print(f"Deleted old rows from stock_selection: {result}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(cleanup())
