import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def migrate():
    # 2026-02-14 修正：宿主机运行使用 localhost
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        host = os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST")
        port = os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        db = os.getenv("DB_NAME")
        missing = [k for k, v in (("DB_HOST", host), ("DB_PORT", port), ("DB_USER", user), ("DB_PASSWORD", password), ("DB_NAME", db)) if not v]
        if missing:
            raise RuntimeError(f"Missing DB env vars: {', '.join(missing)}. Please set DATABASE_URL or DB_* in root .env")
        db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"

    engine = create_async_engine(db_url)

    table_sql = """
    CREATE TABLE IF NOT EXISTS system_settings (
        id SERIAL PRIMARY KEY,
        config_key VARCHAR(100) NOT NULL,
        config_value TEXT NOT NULL,
        service_name VARCHAR(50) DEFAULT 'global',
        category VARCHAR(50) DEFAULT 'general',
        description TEXT,
        is_secret BOOLEAN DEFAULT FALSE,
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(config_key, service_name)
    );
    """

    index_sql = "CREATE INDEX IF NOT EXISTS idx_settings_service ON system_settings(service_name);"

    async with engine.begin() as conn:
        # 分开执行，兼容 asyncpg
        await conn.execute(text(table_sql))
        await conn.execute(text(index_sql))
        print("✅ system_settings 配置表初始化完成")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
