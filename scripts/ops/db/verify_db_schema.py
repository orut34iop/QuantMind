import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def verify():
    conn = await asyncpg.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_MASTER_HOST", "127.0.0.1").strip(),
        port=os.getenv("DB_MASTER_PORT", "5432").strip(),
    )

    rows = await conn.fetch(
        "SELECT tablename FROM pg_catalog.pg_tables WHERE tablename = 'stock_selection';"
    )
    print("\nExisting Tables:")
    for row in rows:
        print(f"- {row['tablename']}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(verify())
