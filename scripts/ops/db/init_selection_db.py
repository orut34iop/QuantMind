import asyncio
import os
import logging

import asyncpg
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database Config
DB_HOST = (os.getenv("DB_MASTER_HOST") or "127.0.0.1").strip()
DB_PORT = (os.getenv("DB_MASTER_PORT") or "5432").strip()
DB_USER = (os.getenv("DB_USER") or "quantmind").strip()
DB_PASSWORD = (os.getenv("DB_PASSWORD") or "admin123").strip()
DB_NAME = (os.getenv("DB_NAME") or "quantmind").strip()

print(
    f"DEBUG: Params - host={repr(DB_HOST)}, port={repr(DB_PORT)}, user={repr(DB_USER)}, db={repr(DB_NAME)}"
)

SCHEMA_SQL = """
-- Enable TimescaleDB if available (Optional, strictly standard PG for now)
-- CREATE EXTENSION IF NOT EXISTS timescaledb;

DROP TABLE IF EXISTS stock_selection CASCADE;

CREATE TABLE stock_selection (
    trade_date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(50),

    -- Valuation Indicators
    pe_ratio DECIMAL(10, 2),        -- PE Ratio
    pb_ratio DECIMAL(10, 2),        -- PB Ratio
    ps_ratio DECIMAL(10, 2),        -- PS Ratio

    -- Market Cap & Flow
    close DECIMAL(10, 2),           -- Close Price (New)
    market_cap DECIMAL(20, 2),      -- Total Market Cap (万元)
    float_share_ratio DECIMAL(6, 4),-- Float share ratio (e.g. 0.30)
    volume BIGINT,                  -- Volume
    amount DECIMAL(20, 2),          -- Amount (New)
    turnover_rate DECIMAL(6, 4),    -- Turnover Rate
    pct_chg DECIMAL(10, 4),         -- Price Change Percentage (New)

    -- Financials & Growth
    roe DECIMAL(6, 4),              -- ROE
    net_profit_growth DECIMAL(10, 4),-- Net Profit Growth Rate (New)
    is_listed_over_1y INTEGER,      -- Listed > 1 year (1=Yes, 0=No)

    -- Industry & Status (New)
    industry VARCHAR(100),          -- Industry
    is_st INTEGER DEFAULT 0,        -- Is ST (1=Yes, 0=No)
    is_suspended INTEGER DEFAULT 0, -- Is Suspended (1=Yes, 0=No)

    -- Technical Indicators
    kdj_k DECIMAL(10, 4),
    kdj_d DECIMAL(10, 4),
    kdj_j DECIMAL(10, 4),

    macd_dif DECIMAL(10, 4),
    macd_dea DECIMAL(10, 4),
    macd_hist DECIMAL(10, 4),

    sma5 DECIMAL(10, 2),
    sma20 DECIMAL(10, 2),
    sma60 DECIMAL(10, 2),

    rsi DECIMAL(10, 4),             -- RSI

    PRIMARY KEY (trade_date, symbol)
);

-- Indices for common filters
CREATE INDEX idx_selection_date ON stock_selection (trade_date);
CREATE INDEX idx_selection_pe ON stock_selection (trade_date, pe_ratio);
CREATE INDEX idx_selection_mkt_cap ON stock_selection (trade_date, market_cap);
CREATE INDEX idx_selection_volume ON stock_selection (trade_date, volume);
CREATE INDEX idx_selection_pct_chg ON stock_selection (trade_date, pct_chg);
CREATE INDEX idx_selection_industry ON stock_selection (industry);
CREATE INDEX idx_selection_status ON stock_selection (is_st, is_suspended);
"""


async def main():
    logger.info("Connecting to database...")
    try:
        conn = await asyncpg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT,
        )
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return

    try:
        # 1. Create Main Table
        logger.info("Initializing schema...")
        await conn.execute(SCHEMA_SQL)

        logger.info("Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"Error during initialization: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
