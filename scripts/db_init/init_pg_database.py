#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PostgreSQL数据库初始化脚本
用于创建QMT缓存系统所需的数据库表结构
"""

import os
from datetime import datetime

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# PostgreSQL连接配置
DB_CONFIG = {
    # Prefer unified DB_* env vars from root .env
    "host": os.getenv("DB_MASTER_HOST") or os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_MASTER_PORT") or os.getenv("DB_PORT") or 5432),
    "user": os.getenv("DB_USER", "quantmind"),
    "password": os.getenv("DB_PASSWORD", "admin123"),
    "database": os.getenv("DB_NAME", "quantmind"),
}

# 表结构SQL
CREATE_TABLES_SQL = """
-- 账户资产表
CREATE TABLE IF NOT EXISTS qmt_account_assets (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    total_asset DECIMAL(20, 2),
    available_cash DECIMAL(20, 2),
    market_value DECIMAL(20, 2),
    frozen_cash DECIMAL(20, 2),
    withdrawable_cash DECIMAL(20, 2),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_account_timestamp UNIQUE(account_id, timestamp)
);

-- 持仓明细表
CREATE TABLE IF NOT EXISTS qmt_positions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(50),
    volume BIGINT,
    available_volume BIGINT,
    avg_price DECIMAL(10, 4),
    current_price DECIMAL(10, 4),
    market_value DECIMAL(20, 2),
    profit_loss DECIMAL(20, 2),
    profit_loss_ratio DECIMAL(10, 4),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_position_timestamp UNIQUE(account_id, stock_code, timestamp)
);

-- 当日委托表
CREATE TABLE IF NOT EXISTS qmt_orders (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    order_id VARCHAR(50) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(50),
    order_type VARCHAR(20),
    order_status VARCHAR(20),
    price DECIMAL(10, 4),
    volume BIGINT,
    filled_volume BIGINT,
    order_time TIMESTAMP,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_order_timestamp UNIQUE(account_id, order_id, timestamp)
);

-- 当日成交表
CREATE TABLE IF NOT EXISTS qmt_trades (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    trade_id VARCHAR(50) NOT NULL,
    order_id VARCHAR(50),
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(50),
    trade_type VARCHAR(20),
    price DECIMAL(10, 4),
    volume BIGINT,
    amount DECIMAL(20, 2),
    trade_time TIMESTAMP,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_trade_timestamp UNIQUE(account_id, trade_id, timestamp)
);

-- 系统日志表
CREATE TABLE IF NOT EXISTS qmt_sync_logs (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    duration_ms INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_account_assets_timestamp ON qmt_account_assets(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_account_assets_account_id ON qmt_account_assets(account_id);

CREATE INDEX IF NOT EXISTS idx_positions_timestamp ON qmt_positions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_positions_account_stock ON qmt_positions(account_id, stock_code);

CREATE INDEX IF NOT EXISTS idx_orders_timestamp ON qmt_orders(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_orders_account_id ON qmt_orders(account_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON qmt_orders(order_status);

CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON qmt_trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_account_id ON qmt_trades(account_id);

CREATE INDEX IF NOT EXISTS idx_sync_logs_timestamp ON qmt_sync_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sync_logs_type_status ON qmt_sync_logs(sync_type, status);

-- 创建数据清理函数(保留最近7天数据)
CREATE OR REPLACE FUNCTION cleanup_old_qmt_data()
RETURNS void AS $$
BEGIN
    DELETE FROM qmt_account_assets WHERE timestamp < NOW() - INTERVAL '7 days';
    DELETE FROM qmt_positions WHERE timestamp < NOW() - INTERVAL '7 days';
    DELETE FROM qmt_orders WHERE timestamp < NOW() - INTERVAL '7 days';
    DELETE FROM qmt_trades WHERE timestamp < NOW() - INTERVAL '7 days';
    DELETE FROM qmt_sync_logs WHERE timestamp < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;
"""


def init_database():
    """初始化数据库"""
    try:
        # 连接到PostgreSQL
        print(f"正在连接到PostgreSQL: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        print("开始创建数据库表结构...")

        # 执行SQL
        cursor.execute(CREATE_TABLES_SQL)

        # 验证表是否创建成功
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE 'qmt_%'
            ORDER BY table_name;
        """)

        tables = cursor.fetchall()
        print(f"\n成功创建 {len(tables)} 个表:")
        for table in tables:
            print(f"  ✓ {table[0]}")

        # 记录初始化日志
        cursor.execute("""
            INSERT INTO qmt_sync_logs (sync_type, status, message)
            VALUES ('database_init', 'success', '数据库初始化完成')
        """)

        print(f"\n数据库初始化完成! 时间: {datetime.now()}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ 数据库初始化失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = init_database()
    exit(0 if success else 1)
