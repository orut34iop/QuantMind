from backend.strategy_service.app.config import get_settings
from backend.strategy_service.app.models.strategy import Base
import sys
from pathlib import Path
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))



async def init_db():
    # Load .env from backend/strategy_service
    env_path = project_root / "backend/strategy_service/.env"
    load_dotenv(env_path)

    settings = get_settings()
<<<<<<< HEAD
    print(
        f"Connecting to: {settings.DATABASE_URL.split('@')[1]}"
    )  # Print host only for safety
=======
    # Print host only for safety
    print(f"Connecting to: {settings.DATABASE_URL.split('@')[1]}")
>>>>>>> refactor/service-cleanup

    engine = create_async_engine(settings.DATABASE_URL)

    async with engine.begin() as conn:
        print("Dropping tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating tables...")
        # Create all tables defined in Base (Strategy, Backtest, etc)
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
