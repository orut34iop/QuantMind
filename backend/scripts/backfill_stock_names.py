import json
import asyncio
import os
import psycopg2
from pathlib import Path

def get_db_params():
    # Attempt to read from .env in project root
    env_path = Path("/Users/qusong/git/quantmind/.env")
    params = {}
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    params[key] = val
    
    # Priority: Env vars > .env
    return {
        "dbname": os.getenv("DB_NAME", params.get("DB_NAME", "quantmind")),
        "user": os.getenv("DB_USER", params.get("DB_USER", "quantmind")),
        "password": os.getenv("DB_PASSWORD", params.get("DB_PASSWORD", "quantmind2026")),
        "host": os.getenv("DB_HOST", params.get("DB_HOST", "210.16.175.87")),
        "port": os.getenv("DB_PORT", params.get("DB_PORT", "5432")),
    }

def backfill():
    index_path = "/Users/qusong/git/quantmind/data/stocks/stocks_index.json"
    if not os.path.exists(index_path):
        print(f"Index file not found: {index_path}")
        return

    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    symbol_to_name = {item["symbol"]: item["name"] for item in data.get("items", [])}
    print(f"Loaded {len(symbol_to_name)} symbols from index.")

    db_params = get_db_params()
    try:
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor()

        # Update orders
        print("Backfilling orders...")
        cur.execute("SELECT order_id, symbol FROM orders WHERE symbol_name IS NULL")
        orders = cur.fetchall()
        updated_orders = 0
        for order_id, symbol in orders:
            name = symbol_to_name.get(symbol)
            if name:
                cur.execute("UPDATE orders SET symbol_name = %s WHERE order_id = %s", (name, order_id))
                updated_orders += 1
        
        # Update trades
        print("Backfilling trades...")
        cur.execute("SELECT id, symbol FROM trades WHERE symbol_name IS NULL")
        trades = cur.fetchall()
        updated_trades = 0
        for trade_id, symbol in trades:
            name = symbol_to_name.get(symbol)
            if name:
                cur.execute("UPDATE trades SET symbol_name = %s WHERE id = %s", (name, trade_id))
                updated_trades += 1

        conn.commit()
        print(f"Successfully updated {updated_orders} orders and {updated_trades} trades.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    backfill()
